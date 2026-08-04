import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import LoginModal from '@/components/modals/LoginModal';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isAuthenticated, isLoading } = useAuth();
  const [showLogin, setShowLogin] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      setShowLogin(true);
    } else if (isAuthenticated) {
      setShowLogin(false);
    }
  }, [isLoading, isAuthenticated]);

  const handleOpenChange = (open: boolean) => {
    setShowLogin(open);
    if (!open) {
      navigate('/'); // Redirect to public home if they close the login modal
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <>
      {isAuthenticated ? children : null}
      <LoginModal 
        open={showLogin} 
        onOpenChange={handleOpenChange} 
        canClose={true} 
      />
    </>
  );
};

export default ProtectedRoute;
