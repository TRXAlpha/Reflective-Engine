import React from 'react';
import ReactDOM from 'react-dom/client';
import GhostWebUI from './GhostWebUI';
import './index.css'; // <-- this imports Tailwind

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <GhostWebUI />
  </React.StrictMode>
);
