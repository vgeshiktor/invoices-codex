import { BrowserRouter } from 'react-router-dom';
import { AuthStubProvider } from './app/authStub';
import { AppRoutes } from './routes/AppRoutes';
import './App.css';

function App() {
  return (
    <AuthStubProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthStubProvider>
  );
}

export default App;
