 import { useState } from 'react';
 import { useNavigate } from 'react-router-dom';
 import { useAuth } from '@/hooks/useAuth';
 import { Button } from '@/components/ui/button';
 import { Input } from '@/components/ui/input';
 import { Label } from '@/components/ui/label';
 import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
 import { useToast } from '@/hooks/use-toast';
 
 type AuthMode = 'signin' | 'reset';
 
 const Login = () => {
   const [mode, setMode] = useState<AuthMode>('signin');
   const [email, setEmail] = useState('');
   const [password, setPassword] = useState('');
   const [loading, setLoading] = useState(false);
   const { signIn, resetPassword } = useAuth();
   const navigate = useNavigate();
   const { toast } = useToast();
 
   const handleSubmit = async (e: React.FormEvent) => {
     e.preventDefault();
     setLoading(true);
 
     try {
       if (mode === 'reset') {
         const { error } = await resetPassword(email);
         if (error) throw error;
         toast({
           title: 'Check your email',
           description: 'We sent you a password reset link.',
         });
         setMode('signin');
       } else {
         const { error } = await signIn(email, password);
         if (error) throw error;
         navigate('/dashboard');
       }
     } catch (error: unknown) {
       const message = error instanceof Error ? error.message : 'An error occurred';
       toast({
         title: 'Error',
         description: message,
         variant: 'destructive',
       });
     } finally {
       setLoading(false);
     }
   };
 
   const getTitle = () => {
     return mode === 'reset' ? 'Reset password' : 'Sign in';
   };
 
   const getDescription = () => {
     return mode === 'reset' 
       ? 'Enter your email to receive a reset link' 
       : 'Enter your credentials to access your account';
   };
 
   return (
     <div className="flex min-h-screen items-center justify-center bg-background p-4">
       <Card className="w-full max-w-sm border-border bg-card">
         <CardHeader className="space-y-1 text-center">
           <CardTitle className="text-2xl font-semibold tracking-tight text-foreground">
             {getTitle()}
           </CardTitle>
           <CardDescription className="text-muted-foreground">
             {getDescription()}
           </CardDescription>
         </CardHeader>
         <CardContent>
           <form onSubmit={handleSubmit} className="space-y-4">
             <div className="space-y-2">
               <Label htmlFor="email" className="text-foreground">Email</Label>
               <Input
                 id="email"
                 type="email"
                 placeholder="name@example.com"
                 value={email}
                 onChange={(e) => setEmail(e.target.value)}
                 required
                 className="bg-background border-border"
               />
             </div>
             
             {mode !== 'reset' && (
               <div className="space-y-2">
                 <Label htmlFor="password" className="text-foreground">Password</Label>
                 <Input
                   id="password"
                   type="password"
                   placeholder="••••••••"
                   value={password}
                   onChange={(e) => setPassword(e.target.value)}
                   required
                   minLength={6}
                   className="bg-background border-border"
                 />
               </div>
             )}
 
             <Button type="submit" className="w-full" disabled={loading}>
               {loading ? 'Please wait...' : getTitle()}
             </Button>
           </form>
 
           <div className="mt-4 space-y-2 text-center text-sm">
             {mode === 'signin' && (
               <button
                 type="button"
                 onClick={() => setMode('reset')}
                 className="text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
               >
                 Forgot password?
               </button>
             )}
             
             {mode === 'reset' && (
               <button
                 type="button"
                 onClick={() => setMode('signin')}
                 className="text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
               >
                 Back to sign in
               </button>
             )}
           </div>
         </CardContent>
       </Card>
     </div>
   );
 };
 
 export default Login;