import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchTests, fetchTestAttempts } from '../../api/api';
import './Analytics.css';

const Analytics = () => {
  const [activeTab, setActiveTab] = useState('progress');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({
    materialsStudied: 0,
    totalMaterials: 0,
    testsCompleted: 0,
    totalTests: 0,
    averageScore: 0,
    totalPoints: 0,
    streakDays: 0,
  });
  const [testResults, setTestResults] = useState([]);
  const navigate = useNavigate();

  const renderProgressBar = (p) => (
    <div className="progress-bar">
      <div className="progress-fill" style={{ width: `${p}%` }} />
    </div>
  );

  useEffect(() => {
    const load = async () => {
      try {
        const tests = await fetchTests();
        const results = [];
        let completed = 0,
          totalScore = 0;
        for (const test of tests) {
          try {
            const attempts = await fetchTestAttempts(test.id);
            const completedAttempts = (attempts || []).filter((a) => a.status === 'completed');
            if (completedAttempts.length) {
              const last = completedAttempts.sort(
                (a, b) =>
                  new Date(b.completed_at || b.submitted_at) -
                  new Date(a.completed_at || a.submitted_at)
              )[0];
              const userScore = last.score || 0;
              const percent = test.max_score ? Math.round((userScore / test.max_score) * 100) : 0;
              const date =
                last.completed_at || last.submitted_at
                  ? new Date(last.completed_at || last.submitted_at).toLocaleDateString('ru-RU')
                  : '—';
              results.push({
                id: test.id,
                name: test.title,
                score: percent,
                date,
                userScore,
                maxScore: test.max_score,
              });
              completed++;
              totalScore += percent;
            }
          } catch (e) {}
        }
        const avg = completed ? Math.round(totalScore / completed) : 0;
        setStats({
          materialsStudied: 0,
          totalMaterials: 0,
          testsCompleted: completed,
          totalTests: tests.length,
          averageScore: avg,
          totalPoints: 0,
          streakDays: 0,
        });
        setTestResults(results);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleBack = () => navigate('/personal-account');
  if (loading) return <div className="loading">Загрузка аналитики...</div>;
  if (error) return <div className="error">Ошибка: {error}</div>;

  return (
    <div className="analytics-page">
      <div className="analytics-container">
        <div className="analytics-header">
          <button className="back-button" onClick={handleBack}>
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
                {renderProgressBar(0)}
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
                  {testResults.length === 0 ? (
                    <tr>
                      <td colSpan="3">Нет пройденных тестов</td>
                    </tr>
                  ) : (
                    testResults.map((t) => (
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
