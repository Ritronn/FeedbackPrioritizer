import React, { useState, useEffect } from 'react';
import './Home.css'
import { 
  Upload, Send, MessageSquare, AlertCircle, TrendingUp, 
  Mail, Slack, CheckCircle, XCircle, Clock, BarChart3 
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';
import './Home.css';
import { Link } from 'react-router-dom';
import Chatbot from './Chatbot';
<div className="flex gap-4">
  <Link 
    to="/auto-fetch" 
    className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
  >
    🔗 Auto-Fetch from Sources
  </Link>
  
  <button className="px-6 py-3 bg-green-600 text-white rounded-lg">
    📤 Upload CSV
  </button>
</div>

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Title, Tooltip, Legend);

const API_URL = process.env.REACT_APP_API_URL || 'https://feedbackprioritizer-production-425f.up.railway.app';


function Home() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sendingReport, setSendingReport] = useState(false);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/dashboard`);
      const data = await response.json();
      setDashboardData(data);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) {
      alert('Please select a file first!');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();
      
      if (result.success) {
        alert(`✅ ${result.message}`);
        fetchDashboard();
        setFile(null);
      } else {
        alert(`❌ ${result.error}`);
      }
    } catch (error) {
      alert('Upload failed! Make sure backend is running.');
      console.error(error);
    }
    setUploading(false);
  };

  const handleSendReport = async () => {
    setSendingReport(true);
    try {
      const response = await fetch(`${API_URL}/send-email`, {
        method: 'POST',
      });

      const result = await response.json();
      
      if (result.success) {
        alert('✅ Report sent to Email & Slack!');
      } else {
        alert(`❌ ${result.error}`);
      }
    } catch (error) {
      alert('Failed to send report!');
      console.error(error);
    }
    setSendingReport(false);
  };

  const urgencyChartData = dashboardData ? {
    labels: ['Critical', 'High', 'Medium', 'Low'],
    datasets: [{
      label: 'Feedback by Urgency',
      data: [
        dashboardData.stats.by_urgency.critical,
        dashboardData.stats.by_urgency.high,
        dashboardData.stats.by_urgency.medium,
        dashboardData.stats.by_urgency.low
      ],
      backgroundColor: ['#EF4444', '#F59E0B', '#3B82F6', '#10B981'],
    }]
  } : null;

  const sentimentChartData = dashboardData ? {
    labels: ['Positive', 'Negative', 'Neutral'],
    datasets: [{
      data: [
        dashboardData.stats.by_sentiment.positive,
        dashboardData.stats.by_sentiment.negative,
        dashboardData.stats.by_sentiment.neutral
      ],
      backgroundColor: ['#10B981', '#EF4444', '#6B7280'],
    }]
  } : null;

  const categoryChartData = dashboardData ? {
    labels: Object.keys(dashboardData.stats.by_category),
    datasets: [{
      label: 'Feedback by Category',
      data: Object.values(dashboardData.stats.by_category),
      backgroundColor: '#8B5CF6',
    }]
  } : null;

  return (
    <div>
      <Chatbot/>
    <div className="home-container">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <BarChart3 size={32} />
            <h1>Feedback Prioritizer</h1>
          </div>
          <p className="tagline">AI-Powered Customer Insights Dashboard</p>
        </div>
      </header>

      {/* Upload Section */}
      <section className="upload-section">
        <div className="upload-card">
          <Upload className="upload-icon" size={48} />
          <h2>Upload Feedback CSV</h2>
          <p>Upload your customer feedback file to get instant AI-powered analysis</p>
          
          <div className="upload-controls">
            <label className="file-input-label">
              <input 
                type="file" 
                accept=".csv" 
                onChange={handleFileChange}
                className="file-input"
              />
              {file ? file.name : 'Choose CSV File'}
            </label>
            
            <button 
              onClick={handleUpload} 
              disabled={!file || uploading}
              className="btn-primary"
            >
              {uploading ? 'Analyzing...' : 'Upload & Analyze'}
            </button>
          </div>
        </div>
      </section>

      {/* Dashboard */}
      {loading ? (
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading dashboard...</p>
        </div>
      ) : dashboardData ? (
        <>
          {/* Stats Cards */}
          <section className="stats-grid">
            <div className="stat-card purple">
              <MessageSquare size={32} />
              <div className="stat-content">
                <h3>Total Feedback</h3>
                <p className="stat-value">{dashboardData.stats.total_feedback}</p>
              </div>
            </div>

            <div className="stat-card red">
              <AlertCircle size={32} />
              <div className="stat-content">
                <h3>Critical Issues</h3>
                <p className="stat-value">{dashboardData.stats.by_urgency.critical}</p>
              </div>
            </div>

            <div className="stat-card green">
              <CheckCircle size={32} />
              <div className="stat-content">
                <h3>Positive Feedback</h3>
                <p className="stat-value">{dashboardData.stats.by_sentiment.positive}</p>
              </div>
            </div>

            <div className="stat-card orange">
              <TrendingUp size={32} />
              <div className="stat-content">
                <h3>Avg Priority</h3>
                <p className="stat-value">{dashboardData.stats.avg_priority_score.toFixed(0)}</p>
              </div>
            </div>
          </section>

          {/* Charts Section */}
          <section className="charts-section">
            <div className="chart-card">
              <h3>📊 Urgency Distribution</h3>
              {urgencyChartData && <Bar data={urgencyChartData} options={{
                responsive: true,
                plugins: { legend: { display: false } }
              }} />}
            </div>

            <div className="chart-card">
              <h3>😊 Sentiment Analysis</h3>
              {sentimentChartData && <Doughnut data={sentimentChartData} />}
            </div>

            <div className="chart-card full-width">
              <h3>🏷️ Category Breakdown</h3>
              {categoryChartData && <Bar data={categoryChartData} options={{
                responsive: true,
                plugins: { legend: { display: false } }
              }} />}
            </div>
          </section>

          {/* Top Priority Issues */}
          <section className="priority-section">
            <h2>🔥 Top Priority Issues</h2>
            <div className="issues-list">
              {dashboardData.top_priority.map((issue, idx) => (
                <div key={idx} className={`issue-card urgency-${issue.urgency_level}`}>
                  <div className="issue-header">
                    <span className="priority-badge">Priority: {issue.priority_score}</span>
                    <span className="category-badge">{issue.category}</span>
                  </div>
                  <h4>{issue.key_issue}</h4>
                  <p className="issue-action">💡 {issue.suggested_action}</p>
                  <div className="issue-meta">
                    <span className="source-badge">{issue.source || 'CSV'}</span>
                    <span className="sentiment">{issue.sentiment}</span>
                    <span className="urgency">{issue.urgency_level}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Send Report Section */}
          <section className="report-section">
            <div className="report-card">
              <h2>📤 Send Weekly Report</h2>
              <p>Deliver priority insights to your team via Email & Slack</p>
              <button 
                onClick={handleSendReport} 
                disabled={sendingReport}
                className="btn-send"
              >
                {sendingReport ? (
                  <>
                    <Clock className="spin" size={20} />
                    Sending...
                  </>
                ) : (
                  <>
                    <Mail size={20} />
                    <Slack size={20} />
                    Send Report Now
                  </>
                )}
              </button>
            </div>
          </section>
        </>
      ) : (
        <div className="empty-state">
          <Upload size={64} />
          <h2>No Data Yet</h2>
          <p>Upload your first CSV file to see insights</p>
        </div>
      )}
    </div>
    </div>
  );
}

export default Home;