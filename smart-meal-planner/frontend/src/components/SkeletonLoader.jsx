import React from 'react';
import { clsx } from 'clsx';

const SkeletonLoader = ({ className, count = 1 }) => {
  const skeletons = Array.from({ length: count }, (_, i) => (
    <div
      key={i}
      className={clsx('animate-pulse bg-gray-200 rounded-md', className)}
    />
  ));

  return <>{skeletons}</>;
};

export default SkeletonLoader;
