import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';
import { DatasetMetadata, HealthResponse } from '../api/types';

interface DatasetContextType {
  selectedDatasetId: string | null;
  setSelectedDatasetId: (id: string | null) => void;
  restaurantId: string;
  setRestaurantId: (id: string) => void;
  restaurantName: string;
  setRestaurantName: (name: string) => void;
  isDemoAuthenticated: boolean;
  enterDemoWorkspace: (name: string, customTenantId?: string) => void;
  exitDemoWorkspace: () => void;
  datasets: DatasetMetadata[];
  loadingDatasets: boolean;
  refreshDatasets: () => Promise<void>;
  backendHealth: HealthResponse | null;
  isBackendConnected: boolean;
  checkHealth: () => Promise<void>;
}

const DatasetContext = createContext<DatasetContextType | undefined>(undefined);

export const DatasetProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [restaurantName, setRestaurantName] = useState<string>(() => {
    return sessionStorage.getItem('rasaiq_demo_restaurant_name') || 'Dakshin Heritage Cafe';
  });
  const [restaurantId, setRestaurantId] = useState<string>(() => {
    return sessionStorage.getItem('rasaiq_demo_restaurant_id') || 'default_restaurant';
  });
  const [isDemoAuthenticated, setIsDemoAuthenticated] = useState<boolean>(() => {
    return sessionStorage.getItem('rasaiq_demo_entered') === 'true';
  });
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [loadingDatasets, setLoadingDatasets] = useState<boolean>(false);
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);

  const enterDemoWorkspace = useCallback((name: string, customTenantId?: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const tenant = customTenantId?.trim() || 'default_restaurant';
    setRestaurantName(trimmed);
    setRestaurantId(tenant);
    setIsDemoAuthenticated(true);
    try {
      sessionStorage.setItem('rasaiq_demo_restaurant_name', trimmed);
      sessionStorage.setItem('rasaiq_demo_restaurant_id', tenant);
      sessionStorage.setItem('rasaiq_demo_entered', 'true');
    } catch {
      // Storage access may be restricted
    }
  }, []);

  const exitDemoWorkspace = useCallback(() => {
    setIsDemoAuthenticated(false);
    try {
      sessionStorage.removeItem('rasaiq_demo_entered');
    } catch {
      // Storage access may be restricted
    }
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const res = await apiClient.getHealth();
      setBackendHealth(res);
      setIsBackendConnected(res.status === 'ok' && res.database === 'connected');
    } catch {
      setIsBackendConnected(false);
      setBackendHealth(null);
    }
  }, []);

  const refreshDatasets = useCallback(async () => {
    setLoadingDatasets(true);
    try {
      const res = await apiClient.listDatasets(restaurantId);
      if (res && res.datasets) {
        setDatasets(res.datasets);
      }
    } catch {
      // Failed to load datasets, keep empty
    } finally {
      setLoadingDatasets(false);
    }
  }, [restaurantId]);

  useEffect(() => {
    checkHealth();
    refreshDatasets();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [checkHealth, refreshDatasets]);

  return (
    <DatasetContext.Provider
      value={{
        selectedDatasetId,
        setSelectedDatasetId,
        restaurantId,
        setRestaurantId,
        restaurantName,
        setRestaurantName,
        isDemoAuthenticated,
        enterDemoWorkspace,
        exitDemoWorkspace,
        datasets,
        loadingDatasets,
        refreshDatasets,
        backendHealth,
        isBackendConnected,
        checkHealth,
      }}
    >
      {children}
    </DatasetContext.Provider>
  );
};

export const useDataset = (): DatasetContextType => {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error('useDataset must be used within a DatasetProvider');
  }
  return context;
};
