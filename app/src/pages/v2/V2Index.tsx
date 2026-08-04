import React from 'react';
import { Routes, Route } from 'react-router-dom';
import V2Layout from '@/components/v2/V2Layout';
import V2Home from './V2Home';
import V2Workspace from './V2Workspace';
import V2Databases from './V2Databases';
import V2Settings from './V2Settings';

import ProtectedRoute from '@/components/auth/ProtectedRoute';

const V2Index = () => {
  return (
    <V2Layout>
      <Routes>
        <Route path="/" element={<V2Home />} />
        <Route path="/workspace" element={
          <ProtectedRoute>
            <V2Workspace />
          </ProtectedRoute>
        } />
        <Route path="/databases" element={
          <ProtectedRoute>
            <V2Databases />
          </ProtectedRoute>
        } />
        <Route path="/settings" element={
          <ProtectedRoute>
            <V2Settings />
          </ProtectedRoute>
        } />
      </Routes>
    </V2Layout>
  );
};

export default V2Index;
