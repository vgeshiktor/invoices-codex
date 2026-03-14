import { useNavigate } from 'react-router-dom';
import { useAuthStub } from '../app/authStub.context';

export function LoginPage() {
  const navigate = useNavigate();
  const { signIn } = useAuthStub();

  const handleSignIn = () => {
    signIn();
    navigate('/dashboard', { replace: true });
  };

  return (
    <main className="route-status">
      <h1>Login</h1>
      <p>This is a Week 1 auth stub. Real auth/session wiring lands in Week 2.</p>
      <button className="shell__button" onClick={handleSignIn} type="button">
        Sign in (stub)
      </button>
    </main>
  );
}
