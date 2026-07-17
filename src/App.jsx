import React, { Suspense } from 'react';
import { Routes, Route, Navigate, useParams } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { canAccessBranch, isUserAdmin } from './config/authConfig';
import { BranchDataProvider } from './context/BranchDataContext';
import LoginPage from './pages/LoginPage';

const DashboardPage = React.lazy(() => import('./pages/DashboardPage'));
const AnalyticsPage = React.lazy(() => import('./pages/AnalyticsPage'));
const InventoryPage = React.lazy(() => import('./pages/InventoryPage'));
const OrdersPage = React.lazy(() => import('./pages/OrdersPage'));
const MenuPage = React.lazy(() => import('./pages/MenuPage'));
const ReportsPage = React.lazy(() => import('./pages/ReportsPage'));
const HistoryPage = React.lazy(() => import('./pages/HistoryPage'));
const AdminHomePage = React.lazy(() => import('./pages/AdminHomePage'));

function FullScreenLoader() {
  return (
    <div style={{ display: 'grid', placeItems: 'center', height: '100dvh', background: 'var(--bg)' }}>
      <div className="spinner spinner--lg" aria-label="Loading" />
    </div>
  );
}

function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, initialLoading, user } = useAuth();
  const params = useParams();
  const branchId = params.branchId;

  if (initialLoading) return <FullScreenLoader />;
  if (!isAuthenticated) return <Navigate to="/" replace />;

  const email = user?.email;
  if (isUserAdmin(email)) return children;
  if (adminOnly) return <Navigate to="/" replace />;
  if (branchId && !canAccessBranch(email, branchId)) return <Navigate to="/" replace />;

  return children;
}

/** Provides shared live branch data to every page below a /:branchId route. */
function BranchScope({ children }) {
  const { branchId } = useParams();
  return <BranchDataProvider branchId={branchId}>{children}</BranchDataProvider>;
}

function branchRoute(Page) {
  return (
    <ProtectedRoute>
      <BranchScope>
        <Page />
      </BranchScope>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/home-admin" element={<ProtectedRoute adminOnly><AdminHomePage /></ProtectedRoute>} />
        <Route path="/home/:branchId" element={branchRoute(DashboardPage)} />
        <Route path="/analytics/:branchId" element={branchRoute(AnalyticsPage)} />
        <Route path="/inventory/:branchId" element={branchRoute(InventoryPage)} />
        <Route path="/orders/:branchId" element={branchRoute(OrdersPage)} />
        <Route path="/menu/:branchId" element={branchRoute(MenuPage)} />
        <Route path="/reports/:branchId" element={branchRoute(ReportsPage)} />
        <Route path="/analytics-history/:branchId" element={branchRoute(HistoryPage)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
