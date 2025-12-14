import React from 'react';
import { useNetworkStatus } from '../hooks/useNetworkStatus';
import { WifiOff } from 'lucide-react';

const NetworkStatusIndicator = () => {
  const isOnline = useNetworkStatus();

  if (isOnline) {
    return null;
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-red-600 text-white p-4 text-center flex items-center justify-center z-50">
      <WifiOff className="mr-2" />
      You are currently offline. Some features may be unavailable.
    </div>
  );
};

export default NetworkStatusIndicator;
