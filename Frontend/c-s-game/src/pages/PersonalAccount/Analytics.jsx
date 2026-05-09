// analysis.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchLearningDashboard } from '../../api/api';
import './Analytics.css';

const Analytics = () => {
  const [activeTab, setActiveTab] = useState('progress');
  const navigate = useNavigate();

  const {
    data: dashboard,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['learningDashboard'],
    queryFn: () => fetchLearningDashboard(200),
  });

  if (isLoading) return <div className="loading">Загрузка аналитики...</div>;
  if (error) return <div className="error">Ошибка: {error.message}</div>;

  const stats = {
    materialsStudied: dashboard?.total_materials || 0,
    totalMaterials: dashboard?.total_materials || 0,
    testsCompleted: dashboard?.completed_tests || 0,
    totalTests: dashboard?.total_tests || 0,
    averageScore: dashboard?.average_score_percent || 0,
    totalPoints: 0,
    streakDays: dashboard?.streak_days || 0,
    testResults: (dashboard?.test_results || []).map((t) => ({
      id: t.test_id,
      name: t.title,
      score: t.score_percent || 0,
      date: t.completed_at ? new Date(t.completed_at).toLocaleDateString('ru-RU') : '—',
      userScore: t.score_value || 0,
      maxScore: t.max_score || 0,
    })),
  };

  const renderProgressBar = (p) => (
    <div className="progress-bar">
      <div className="progress-fill" style={{ width: `${p}%` }} />
    </div>
  );

  return (
    <div className="analytics-page">
      <div className="analytics-container">
        <div className="analytics-header">
          <button className="back-button" onClick={() => navigate('/personal-account')}>
            Назад в личный кабинет
          </button>
          <h1>Аналитика обучения</h1>
          <p className="analytics-subtitle">Статистика вашего прогресса и результатов</p>
        </div>
        <div className="analytics-tabs">
          <button
            className={`tab-btn ${activeTab === 'progress' ? 'active' : ''}`}
            onClick={() => setActiveTab('progress')}
          >
            Прогресс
          </button>
          <button
            className={`tab-btn ${activeTab === 'tests' ? 'active' : ''}`}
            onClick={() => setActiveTab('tests')}
          >
            Тесты
          </button>
        </div>
        {activeTab === 'progress' && (
          <div className="analytics-content">
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-header">
                  <h3>Материалы</h3>
                </div>
                <div className="stat-numbers">
                  <span className="stat-current">{stats.materialsStudied}</span>
                  <span className="stat-divider">/</span>
                  <span className="stat-total">{stats.totalMaterials}</span>
                </div>
                {renderProgressBar(
                  stats.totalMaterials ? (stats.materialsStudied / stats.totalMaterials) * 100 : 0
                )}
              </div>
              <div className="stat-card">
                <div className="stat-header">
                  <h3>Тесты</h3>
                </div>
                <div className="stat-numbers">
                  <span className="stat-current">{stats.testsCompleted}</span>
                  <span className="stat-divider">/</span>
                  <span className="stat-total">{stats.totalTests}</span>
                </div>
                {renderProgressBar(
                  stats.totalTests ? (stats.testsCompleted / stats.totalTests) * 100 : 0
                )}
              </div>
              <div className="stat-card">
                <div className="stat-header">
                  <h3>Средний балл (10‑балльная шкала)</h3>
                </div>
                <div className="stat-numbers">
                  <span className="stat-score">{(stats.averageScore / 10).toFixed(1)}</span>
                </div>
                <div className="score-indicator">
                  <div className="score-bar">
                    <div className="score-fill" style={{ width: `${stats.averageScore}%` }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        {activeTab === 'tests' && (
          <div className="analytics-content">
            <div className="test-results-table">
              <h3>Результаты тестов</h3>
              <table>
                <thead>
                  <tr>
                    <th>Название теста</th>
                    <th>Результат</th>
                    <th>Дата прохождения (последняя попытка)</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.testResults.length === 0 ? (
                    <tr>
                      <td colSpan="3">Нет пройденных тестов</td>
                    </tr>
                  ) : (
                    stats.testResults.map((t) => (
                      <tr key={t.id}>
                        <td>{t.name}</td>
                        <td>
                          <div className="test-score-cell">
                            <span className="test-score">{t.score}%</span>
                            {renderProgressBar(t.score)}
                          </div>
                        </td>
                        <td>{t.date}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Analytics;
