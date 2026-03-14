import { BrowserRouter } from 'react-router-dom';
import { AuthSessionProvider } from './app/authSession';
import { AppRoutes } from './routes/AppRoutes';
import './App.css';

function App() {
  return (
    <AuthSessionProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthSessionProvider>
  );
}

export default App;
