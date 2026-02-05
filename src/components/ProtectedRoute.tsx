 import { Navigate } from 'react-router-dom';
 import { useAuth } from '@/hooks/useAuth';
 
 interface ProtectedRouteProps {
   children: React.ReactNode;
 }
 
 const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
   const { user, loading } = useAuth();
 
   if (loading) {
     return (
       <div className="flex min-h-screen items-center justify-center bg-background">
         <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-primary" />
       </div>
     );
   }
 
   if (!user) {
     return <Navigate to="/login" replace />;
   }
 
   return <>{children}</>;
 };
 
 export default ProtectedRoute;