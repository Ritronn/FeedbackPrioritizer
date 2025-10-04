import React, { useState, useEffect } from 'react';
import './DataSources.css';

export default function DataSources() {
  const [config, setConfig] = useState({
    reddit_subreddit: '',
    reddit_query: '',
    google_sheet_url: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [currentConfig, setCurrentConfig] = useState(null);

  useEffect(() => {
    fetchCurrentConfig();
  }, []);

  const fetchCurrentConfig = async () => {
    try {
      const res = await fetch('http://localhost:5000/sources/get');
      const data = await res.json();
      if (data.configured !== false) {
        setCurrentConfig(data);
        setConfig({
          reddit_subreddit: data.reddit_subreddit || '',
          reddit_query: data.reddit_query || '',
          google_sheet_url: data.google_sheet_url || ''
        });
      }
    } catch (err) {
      console.error('Failed to fetch config:', err);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setMessage('');
    
    try {
      const res = await fetch('http://localhost:5000/sources/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      const data = await res.json();
      
      if (data.success) {
        setMessage('Configuration saved successfully!');
        fetchCurrentConfig();
      } else {
        setMessage('Error: ' + data.error);
      }
    } catch (err) {
      setMessage('Failed to save configuration');
    }
    
    setLoading(false);
  };

  const handleTestCollection = async () => {
    setLoading(true);
    setMessage('Testing collection... check console');
    
    try {
      const res = await fetch('http://localhost:5000/test-collection', {
        method: 'POST'
      });
      
      const data = await res.json();
      setMessage(data.success ? 'Collection completed! Check dashboard.' : 'Error: ' + data.error);
    } catch (err) {
      setMessage('Failed to trigger collection');
    }
    
    setLoading(false);
  };

  return (
    <div className="data-sources-container">
      <div className="data-sources-content">
        <h1 className="page-title">Data Sources Configuration</h1>
        <p className="page-subtitle">Configure where to collect feedback from automatically</p>

        {currentConfig?.last_synced && (
          <div className="sync-status">
            <p className="sync-status-text">
              Last synced: {new Date(currentConfig.last_synced).toLocaleString()}
            </p>
          </div>
        )}

        <div className="config-section">
          <h2 className="section-title">Reddit Configuration</h2>
          
          <div className="input-group">
            <label className="input-label">Subreddit Name</label>
            <input
              type="text"
              placeholder="e.g., productivity"
              className="input-field"
              value={config.reddit_subreddit}
              onChange={(e) => setConfig({...config, reddit_subreddit: e.target.value})}
            />
            <p className="input-hint">Enter subreddit name without r/</p>
          </div>

          <div className="input-group">
            <label className="input-label">Search Query</label>
            <input
              type="text"
              placeholder="e.g., feedback, bug, feature request"
              className="input-field"
              value={config.reddit_query}
              onChange={(e) => setConfig({...config, reddit_query: e.target.value})}
            />
            <p className="input-hint">Keywords to search for in posts</p>
          </div>
        </div>

        <div className="config-section">
          <h2 className="section-title">Google Sheets Configuration</h2>
          
          <div className="input-group">
            <label className="input-label">Public Google Sheet URL</label>
            <input
              type="text"
              placeholder="https://docs.google.com/spreadsheets/d/..."
              className="input-field"
              value={config.google_sheet_url}
              onChange={(e) => setConfig({...config, google_sheet_url: e.target.value})}
            />
            <p className="input-hint">
              Sheet must be publicly accessible. Data from Google Forms should be here.
            </p>
          </div>
        </div>

        {message && (
          <div className={`message-box ${message.includes('success') ? 'message-success' : 'message-error'}`}>
            {message}
          </div>
        )}

        <div className="button-group">
          <button
            onClick={handleSave}
            disabled={loading}
            className="btn btn-primary"
          >
            {loading ? 'Saving...' : 'Save Configuration'}
          </button>
          
          <button
            onClick={handleTestCollection}
            disabled={loading || !currentConfig}
            className="btn btn-success"
          >
            {loading ? 'Running...' : 'Test Collection Now'}
          </button>
        </div>

        <div className="info-box">
          <h3 className="info-title">How it works:</h3>
          <ul className="info-list">
            <li>• Configure sources once, system runs automatically every Monday at 9 AM</li>
            <li>• Reddit: Fetches posts from specified subreddit containing your keywords</li>
            <li>• Google Sheets: Reads feedback from your public sheet (e.g., from Google Forms)</li>
            <li>• All data is analyzed and prioritized by AI automatically</li>
          </ul>
        </div>
      </div>
    </div>
  );
}