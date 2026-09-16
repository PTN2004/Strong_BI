import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { WorkspaceProvider } from "@/contexts/WorkspaceContext";
import { DatabaseProvider } from "@/contexts/DatabaseContext";
import { SettingsProvider } from "@/contexts/SettingsContext";
import { ChatProvider } from "@/contexts/ChatContext";

import V4Dashboard from "./pages/v4/V4Dashboard";
import V4Docs from "./pages/v4/V4Docs";
import V4Layout from "./components/v4/V4Layout";
import V4Databases from "./pages/v4/V4Databases";
import V4Semantic from "./pages/v4/V4Semantic";
import V4Settings from "./pages/v4/V4Settings";
import V4SchemaMetadata from "./pages/v4/V4SchemaMetadata";
import V4Conversations from "./pages/v4/V4Conversations";
import V4Dashboards from "./pages/v4/V4Dashboards";
import ProtectedRoute from "./components/auth/ProtectedRoute";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <WorkspaceProvider>
        <DatabaseProvider>
          <SettingsProvider>
            <ChatProvider>
              <TooltipProvider>
                <Toaster />
                <BrowserRouter>
                  <Routes>
                    {/* Root & Core AI Analytics Assistant */}
                    <Route path="/" element={
                      <ProtectedRoute>
                        <V4Layout>
                          <V4Dashboard />
                        </V4Layout>
                      </ProtectedRoute>
                    } />
                    <Route path="/chat" element={
                      <ProtectedRoute>
                        <V4Layout>
                          <V4Dashboard />
                        </V4Layout>
                      </ProtectedRoute>
                    } />
                    <Route path="/v4/dashboard" element={
                      <ProtectedRoute>
                        <V4Layout>
                          <V4Dashboard />
                        </V4Layout>
                      </ProtectedRoute>
                    } />
                    
                    {/* Multi-chart Interactive Dashboards */}
                    <Route path="/dashboards" element={
                      <ProtectedRoute>
                        <V4Layout>
                          <V4Dashboards />
                        </V4Layout>
                      </ProtectedRoute>
                    } />

                    {/* Data Sources, Semantic Layer & Metadata */}
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

                    {/* Conversation History */}
                    <Route path="/conversations" element={
                      <ProtectedRoute>
                        <V4Layout>
                          <V4Conversations />
                        </V4Layout>
                      </ProtectedRoute>
                    } />

                    {/* Settings & User / Business Profile */}
                    <Route path="/settings" element={
                      <ProtectedRoute>
                        <V4Layout>
                          <V4Settings />
                        </V4Layout>
                      </ProtectedRoute>
                    } />

                    {/* Documentation */}
                    <Route path="/docs" element={
                      <ProtectedRoute>
                        <V4Layout>
                          <V4Docs />
                        </V4Layout>
                      </ProtectedRoute>
                    } />

                    {/* Fallback Redirect */}
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </BrowserRouter>
              </TooltipProvider>
            </ChatProvider>
          </SettingsProvider>
        </DatabaseProvider>
      </WorkspaceProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
