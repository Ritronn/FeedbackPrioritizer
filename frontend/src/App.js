import './App.css';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Home from './Pages/Home';
import DataSources from './Pages/DataSources';
import Navbar from './Pages/Navrbar';

function App() {
  return (
    <BrowserRouter>
    <Navbar/>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/sources" element={<DataSources />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;