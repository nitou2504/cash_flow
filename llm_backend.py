"""
Unified LLM backend supporting multiple providers via LiteLLM.
Provides configuration-based model selection and automatic fallbacks.
"""
import os
import yaml
import logging
import time
from typing import Optional, Dict, Any, Tuple

import litellm

# Configure logging
logger = logging.getLogger(__name__)

class LLMBackend:
    """
    Singleton class managing LLM provider connections.

    Features:
    - Multi-provider support (Gemini, Ollama, OpenAI, etc.)
    - Configuration-based model selection
    - Per-function model routing
    - Automatic fallback chains
    - Retry logic with exponential backoff
    """

    _instance = None

    def __init__(self):
        """Initialize backend with configuration."""
        self.config = self._load_config()
        self._configure_litellm()

    @classmethod
    def get_instance(cls) -> 'LLMBackend':
        """
        Get or create singleton instance.

        Returns:
            LLMBackend: The singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration with priority:
        1. YAML file (llm_config.yaml)
        2. Environment variables
        3. Hardcoded defaults (Gemini - backward compatible)

        Returns:
            Dict: Merged configuration
        """
        config = self._get_default_config()

        # Try YAML file
        yaml_path = "llm_config.yaml"
        if os.path.exists(yaml_path):
            try:
                with open(yaml_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        config.update(yaml_config)
                        logger.info(f"Loaded configuration from {yaml_path}")
            except Exception as e:
                logger.warning(f"Failed to load {yaml_path}: {e}. Using defaults.")

        # Override with environment variables
        self._apply_env_overrides(config)

        return config

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Hardcoded defaults - same as current behavior.

        Returns:
            Dict: Default configuration (Gemini only)
        """
        return {
            "default_provider": "gemini",
            "default_model": "gemini-2.5-flash",
            "providers": {
                "gemini": {
                    "type": "litellm",
                    "api_key_env": "GEMINI_API_KEY"
                }
            },
            "timeout_seconds": 30,
            "max_retries": 2,
            "temperature": 0.0
        }

    def _apply_env_overrides(self, config: Dict[str, Any]):
        """
        Override config with environment variables.

        Args:
            config: Configuration dict to modify in-place
        """
        # Global overrides
        if os.getenv("LLM_DEFAULT_PROVIDER"):
            config["default_provider"] = os.getenv("LLM_DEFAULT_PROVIDER")
        if os.getenv("LLM_DEFAULT_MODEL"):
            config["default_model"] = os.getenv("LLM_DEFAULT_MODEL")
        if os.getenv("LLM_OLLAMA_BASE_URL"):
            if "ollama" not in config.get("providers", {}):
                config.setdefault("providers", {})["ollama"] = {}
            config["providers"]["ollama"]["base_url"] = os.getenv("LLM_OLLAMA_BASE_URL")

        # Per-function overrides (format: LLM_<FUNCTION>_MODEL=provider/model)
        function_mapping = {
            "LLM_PRE_PARSE_MODEL": "pre_parse_date_and_account",
            "LLM_TRANSACTION_PARSE_MODEL": "parse_transaction_string",
            "LLM_SUBSCRIPTION_PARSE_MODEL": "parse_subscription_string",
            "LLM_ACCOUNT_PARSE_MODEL": "parse_account_string"
        }

        for env_var, function_name in function_mapping.items():
            value = os.getenv(env_var)
            if value:
                try:
                    provider, model = value.split("/", 1)
                    config.setdefault("function_models", {})[function_name] = {
                        "provider": provider,
                        "model": model
                    }
                except ValueError:
                    logger.warning(f"Invalid format for {env_var}: {value}. Expected 'provider/model'")

    def _configure_litellm(self):
        """Configure LiteLLM global settings."""
        litellm.set_verbose = False  # Reduce noise in logs
        litellm.drop_params = True   # Auto-handle unsupported params
        # Suppress LiteLLM's internal logging unless we're debugging
        litellm.suppress_debug_info = True

    def generate(
        self,
        system_instruction: str,
        user_input: str,
        function_name: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate LLM response with provider routing.

        Args:
            system_instruction: System prompt defining behavior
            user_input: User message to process
            function_name: Function name for routing (optional)
            temperature: Override temperature (optional)

        Returns:
            str: LLM response text

        Raises:
            Exception: If all providers fail after retries
        """
        # Determine which model to use
        provider, model = self._get_model_for_function(function_name)

        # Build messages
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_input}
        ]

        # Get provider config
        provider_config = self.config["providers"].get(provider, {})

        # Build LiteLLM model string and kwargs
        model_str, kwargs = self._build_model_call_params(provider, model, provider_config)

        # Call with fallback
        try:
            return self._call_with_retry(
                model_str,
                messages,
                temperature or self.config.get("temperature", 0.0),
                kwargs
            )
        except Exception as e:
            # Try fallback chain if configured
            if "fallback_chain" in self.config:
                logger.warning(f"Primary model {provider}/{model} failed: {e}")
                return self._try_fallback_chain(messages, temperature, str(e))
            raise

    def _get_model_for_function(self, function_name: Optional[str]) -> Tuple[str, str]:
        """
        Get (provider, model) for given function.

        Priority:
        1. function_models.{function_name} in config
        2. default_provider and default_model

        Args:
            function_name: Name of calling function (optional)

        Returns:
            Tuple[str, str]: (provider, model)
        """
        if function_name and "function_models" in self.config:
            func_config = self.config["function_models"].get(function_name)
            if func_config:
                provider = func_config.get("provider")
                model = func_config.get("model")
                logger.debug(f"Using {provider}/{model} for {function_name}")
                return provider, model

        # Use defaults
        provider = self.config.get("default_provider", "gemini")
        model = self.config.get("default_model", "gemini-2.5-flash")
        logger.debug(f"Using default {provider}/{model}")
        return provider, model

    def _build_model_call_params(
        self,
        provider: str,
        model: str,
        provider_config: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build LiteLLM model string and kwargs for API call.

        Args:
            provider: Provider name (gemini, ollama, etc.)
            model: Model name
            provider_config: Provider configuration dict

        Returns:
            Tuple[str, Dict]: (model_string, kwargs)
        """
        if provider == "gemini":
            model_str = f"gemini/{model}"
            api_key = os.getenv(provider_config.get("api_key_env", "GEMINI_API_KEY"))
            if not api_key:
                raise ValueError(f"GEMINI_API_KEY environment variable not set")
            kwargs = {"api_key": api_key}

        elif provider == "ollama":
            model_str = f"ollama/{model}"
            base_url = provider_config.get("base_url", "http://localhost:3001/v1")
            kwargs = {"api_base": base_url}

        elif provider == "openai":
            model_str = f"openai/{model}"
            api_key = os.getenv(provider_config.get("api_key_env", "OPENAI_API_KEY"))
            if not api_key:
                raise ValueError(f"OPENAI_API_KEY environment variable not set")
            kwargs = {"api_key": api_key}

        else:
            # Generic provider - use model string as-is
            model_str = model
            kwargs = {}
            # Check for api_key_env in config
            if "api_key_env" in provider_config:
                api_key = os.getenv(provider_config["api_key_env"])
                if api_key:
                    kwargs["api_key"] = api_key

        return model_str, kwargs

    def _call_with_retry(
        self,
        model: str,
        messages: list,
        temperature: float,
        kwargs: dict
    ) -> str:
        """
        Call LiteLLM with retry logic.

        Args:
            model: LiteLLM model string
            messages: Message list
            temperature: Temperature parameter
            kwargs: Additional kwargs for completion call

        Returns:
            str: Response text

        Raises:
            Exception: If all retries fail
        """
        max_retries = self.config.get("max_retries", 2)
        timeout = self.config.get("timeout_seconds", 30)

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    timeout=timeout,
                    **kwargs
                )
                return response.choices[0].message.content

            except litellm.RateLimitError as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Rate limit exceeded after {max_retries + 1} attempts")

            except (litellm.Timeout, litellm.APIConnectionError) as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Timeout/connection error, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Connection failed after {max_retries + 1} attempts")

            except Exception as e:
                last_exception = e
                logger.error(f"LLM call failed: {e}")
                # Don't retry on other exceptions (likely config or API errors)
                break

        # All retries exhausted
        raise last_exception if last_exception else Exception("LLM call failed")

    def _try_fallback_chain(
        self,
        messages: list,
        temperature: Optional[float],
        original_error: str
    ) -> str:
        """
        Try fallback providers in order.

        Args:
            messages: Message list
            temperature: Temperature parameter
            original_error: Error message from primary provider

        Returns:
            str: Response text

        Raises:
            Exception: If all fallbacks fail
        """
        fallback_chain = self.config.get("fallback_chain", [])

        for fallback in fallback_chain:
            provider = fallback["provider"]
            model = fallback["model"]

            logger.warning(f"Trying fallback: {provider}/{model}")

            try:
                provider_config = self.config["providers"].get(provider, {})
                model_str, kwargs = self._build_model_call_params(provider, model, provider_config)

                return self._call_with_retry(
                    model_str,
                    messages,
                    temperature or self.config.get("temperature", 0.0),
                    kwargs
                )

            except Exception as e:
                logger.warning(f"Fallback {provider}/{model} failed: {e}")
                continue

        # All fallbacks failed
        raise Exception(f"All providers failed. Original error: {original_error}")
