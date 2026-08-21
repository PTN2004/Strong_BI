import React from 'react';
import { Routes, Route } from 'react-router-dom';
import V2Layout from '@/components/v2/V2Layout';
import V2Home from './V2Home';

import ProtectedRoute from '@/components/auth/ProtectedRoute';

const V2Index = () => {
  return (
    <V2Layout>
      <Routes>
        <Route path="/" element={<V2Home />} />
      </Routes>
    </V2Layout>
  );
};

export default V2Index;
