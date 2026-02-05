 import { useAuth } from '@/hooks/useAuth';
 import { Button } from '@/components/ui/button';
 import { LogOut } from 'lucide-react';
 
 const TopNavbar = () => {
   const { user, signOut } = useAuth();
 
   return (
     <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
       <div className="flex h-14 items-center justify-between px-4 md:px-6">
         <div className="flex items-center gap-2">
           <span className="text-lg font-semibold text-foreground">Dashboard</span>
         </div>
         
         <div className="flex items-center gap-4">
           <span className="hidden text-sm text-muted-foreground sm:inline-block">
             {user?.email}
           </span>
           <Button
             variant="ghost"
             size="sm"
             onClick={signOut}
             className="gap-2"
           >
             <LogOut className="h-4 w-4" />
             <span className="hidden sm:inline-block">Sign out</span>
           </Button>
         </div>
       </div>
     </header>
   );
 };
 
 export default TopNavbar;