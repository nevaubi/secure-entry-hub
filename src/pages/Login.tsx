 import { useState } from 'react';
 import { useNavigate } from 'react-router-dom';
 import { useAuth } from '@/hooks/useAuth';
 import { Button } from '@/components/ui/button';
 import { Input } from '@/components/ui/input';
 import { Label } from '@/components/ui/label';
 import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
 import { useToast } from '@/hooks/use-toast';
 
 type AuthMode = 'signin' | 'signup' | 'reset';
 
 const Login = () => {
   const [mode, setMode] = useState<AuthMode>('signin');
   const [email, setEmail] = useState('');
   const [password, setPassword] = useState('');
   const [loading, setLoading] = useState(false);
   const { signIn, signUp, resetPassword } = useAuth();
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
       } else if (mode === 'signup') {
         const { error } = await signUp(email, password);
         if (error) throw error;
         toast({
           title: 'Check your email',
           description: 'We sent you a confirmation link to verify your account.',
         });
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
     switch (mode) {
       case 'signup': return 'Create account';
       case 'reset': return 'Reset password';
       default: return 'Sign in';
     }
   };
 
   const getDescription = () => {
     switch (mode) {
       case 'signup': return 'Enter your email to create an account';
       case 'reset': return 'Enter your email to receive a reset link';
       default: return 'Enter your credentials to access your account';
     }
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
               <>
                 <button
                   type="button"
                   onClick={() => setMode('reset')}
                   className="text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
                 >
                   Forgot password?
                 </button>
                 <div className="text-muted-foreground">
                   Don't have an account?{' '}
                   <button
                     type="button"
                     onClick={() => setMode('signup')}
                     className="text-foreground hover:underline underline-offset-4"
                   >
                     Sign up
                   </button>
                 </div>
               </>
             )}
             
             {mode === 'signup' && (
               <div className="text-muted-foreground">
                 Already have an account?{' '}
                 <button
                   type="button"
                   onClick={() => setMode('signin')}
                   className="text-foreground hover:underline underline-offset-4"
                 >
                   Sign in
                 </button>
               </div>
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