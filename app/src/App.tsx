import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { DatabaseProvider } from "@/contexts/DatabaseContext";
import { SettingsProvider } from "@/contexts/SettingsContext";
import { ChatProvider } from "@/contexts/ChatContext";

import NotFound from "./pages/NotFound";
import V2Index from "./pages/v2/V2Index";
import V4Dashboard from "./pages/v4/V4Dashboard";
import V4Layout from "./components/v4/V4Layout";
import V4Databases from "./pages/v4/V4Databases";
import V4Semantic from "./pages/v4/V4Semantic";
import V4Settings from "./pages/v4/V4Settings";
import V4SchemaMetadata from "./pages/v4/V4SchemaMetadata";
import ProtectedRoute from "./components/auth/ProtectedRoute";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <DatabaseProvider>
        <SettingsProvider>
          <ChatProvider>
            <TooltipProvider>
              <Toaster />
              <BrowserRouter>
                <Routes>
                  <Route path="/v4/dashboard" element={
                    <ProtectedRoute>
                      <V4Layout>
                        <V4Dashboard />
                      </V4Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/workspace" element={
                    <ProtectedRoute>
                      <V4Layout>
                        <V4Dashboard />
                      </V4Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/databases" element={
                    <ProtectedRoute>
                      <V4Layout>
                        <V4Databases />
                      </V4Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/databases/:graphId/semantic" element={
                    <ProtectedRoute>
                      <V4Layout>
                        <V4Semantic />
                      </V4Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/databases/:graphId/metadata" element={
                    <ProtectedRoute>
                      <V4Layout>
                        <V4SchemaMetadata />
                      </V4Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/settings" element={
                    <ProtectedRoute>
                      <V4Layout>
                        <V4Settings />
                      </V4Layout>
                    </ProtectedRoute>
                  } />
                  <Route path="/*" element={<V2Index />} />
                  {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </BrowserRouter>
            </TooltipProvider>
          </ChatProvider>
        </SettingsProvider>
      </DatabaseProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
