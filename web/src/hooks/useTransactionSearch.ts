import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { SearchFilters, SearchResponse, TimelineTransaction } from '../api/types';

const DEBOUNCE_MS = 300;
const PAGE_SIZE = 50;

export function useTransactionSearch() {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [filters, setFilters] = useState<SearchFilters>({ statuses: ['committed'] });
  const [offset, setOffset] = useState(0);
  const accumulated = useRef<TimelineTransaction[]>([]);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    setOffset(0);
    accumulated.current = [];
  }, [debouncedQuery, filters]);

  const isSearchActive = useMemo(() => {
    return !!(debouncedQuery || filters.account || filters.category || filters.budget
      || filters.from_date || filters.to_date || filters.min_amount || filters.max_amount);
  }, [debouncedQuery, filters]);

  const params = useMemo(() => {
    if (!isSearchActive) return null;
    const p: Record<string, string> = {};
    if (debouncedQuery) p.q = debouncedQuery;
    if (filters.account) p.account = filters.account;
    if (filters.category) p.category = filters.category;
    if (filters.statuses?.length) p.status = filters.statuses.join(',');
    if (filters.budget) p.budget = filters.budget;
    if (filters.from_date) p.from_date = filters.from_date;
    if (filters.to_date) p.to_date = filters.to_date;
    if (filters.min_amount) p.min_amount = filters.min_amount;
    if (filters.max_amount) p.max_amount = filters.max_amount;
    if (filters.date_field && filters.date_field !== 'date_payed') p.date_field = filters.date_field;
    p.limit = String(PAGE_SIZE);
    p.offset = String(offset);
    return p;
  }, [isSearchActive, debouncedQuery, filters, offset]);

  const { data, isLoading, isFetching } = useQuery<SearchResponse>({
    queryKey: ['search', params],
    queryFn: () => api.searchTransactions(params!),
    enabled: !!params,
  });

  const results = useMemo(() => {
    if (!data) return accumulated.current;
    if (offset === 0) {
      accumulated.current = data.results;
    } else {
      const existingIds = new Set(accumulated.current.map(t => t.id));
      const newItems = data.results.filter(t => !existingIds.has(t.id));
      accumulated.current = [...accumulated.current, ...newItems];
    }
    return accumulated.current;
  }, [data, offset]);

  const total = data?.total ?? 0;

  const loadMore = useCallback(() => {
    setOffset(prev => prev + PAGE_SIZE);
  }, []);

  const clearAll = useCallback(() => {
    setQuery('');
    setDebouncedQuery('');
    setFilters({ statuses: ['committed'] });
    setOffset(0);
    accumulated.current = [];
  }, []);

  return {
    query, setQuery,
    filters, setFilters,
    results, total,
    isLoading: isLoading && isSearchActive,
    isFetching,
    isSearchActive,
    hasMore: results.length < total,
    loadMore,
    clearAll,
  };
}
