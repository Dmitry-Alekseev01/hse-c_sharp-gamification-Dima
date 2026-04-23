import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchUserProfile,
  getToken,
  fetchTests,
  fetchUserAnswers,
  fetchMaterials,
} from '../../api/api';
import './PersonalAccount.css';

const PersonalAccount = () => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({
    totalMaterials: 0,
    totalTests: 0,
    completedTests: 0,
    averageScore: 0,
    overallProgress: 0,
  });

  useEffect(() => {
    const loadData = async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const profileData = await fetchUserProfile();
        console.log('Профиль пользователя:', profileData);
        setProfile(profileData);

        const materials = await fetchMaterials();
        const totalMaterials = materials.length;

        const tests = await fetchTests();
        const totalTests = tests.length;
        let completedTests = 0;
        let totalScoreSum = 0;
        let testsWithScore = 0;

        for (const test of tests) {
          try {
            const answers = await fetchUserAnswers(test.id);
            if (answers && answers.length > 0) {
              completedTests++;
              const userScore = answers.reduce((sum, ans) => sum + (ans.score || 0), 0);
              const maxScore = test.max_score;
              if (maxScore) {
                const percentage = (userScore / maxScore) * 100;
                totalScoreSum += percentage;
                testsWithScore++;
              }
            }
          } catch (e) {
          }
        }
        const averageScore = testsWithScore > 0 ? Math.round(totalScoreSum / testsWithScore) : 0;
        const overallProgress = totalTests ? Math.round((completedTests / totalTests) * 100) : 0;

        setStats({
          totalMaterials,
          totalTests,
          completedTests,
          averageScore,
          overallProgress,
        });
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const getRegistrationDate = (profile) => {
    if (!profile) return null;
    const dateString = profile.created_at || profile.registered_at || profile.date_joined || null;
    if (!dateString) return null;
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return null;
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  if (loading) return <div className="loading">Загрузка профиля...</div>;
  if (error) return <div className="error">Ошибка: {error}</div>;
  if (!profile) return <div className="error">Пожалуйста, войдите в систему</div>;

  let displayName = profile.full_name;
  if (!displayName) {
    displayName =
      profile.username && profile.username.includes('@') ? 'Пользователь' : profile.username;
  }
  const loginName = profile.username;
  const registrationDate = getRegistrationDate(profile);

  const materialsDisplay = `0/${stats.totalMaterials}`;
  const testsDisplay = `${stats.completedTests}/${stats.totalTests}`;
  const progressDisplay = `${stats.overallProgress}%`;

  return (
    <div className="personal-account-page">
      <div className="account-header">
        <h1>Личный кабинет</h1>
        <p className="account-subtitle">Управление вашей учётной записью</p>
      </div>
      <div className="account-content">
        <div className="main-content-wrapper">
          <div className="user-info-card">
            <div className="user-avatar-section">
              <div className="user-avatar-large">{displayName.charAt(0).toUpperCase()}</div>
              <div className="user-name-display">
                <h2>{displayName}</h2>
                <span className="user-status">Ученик</span>
              </div>
            </div>
            <div className="user-details">
              <div className="detail-item">
                <div className="detail-label">Имя пользователя:</div>
                <div className="detail-value">{displayName}</div>
              </div>
              <div className="detail-item">
                <div className="detail-label">Логин:</div>
                <div className="detail-value">
                  <span className="login-value">@{loginName}</span>
                </div>
              </div>
              <div className="detail-item">
                <div className="detail-label">Дата регистрации:</div>
                <div className="detail-value">
                  <span className="date-value">{registrationDate || 'Не указана'}</span>
                </div>
              </div>
            </div>
            <div className="account-actions">
              <Link to="/edit-profile" className="action-btn primary-btn">
                Редактировать профиль
              </Link>
              <Link to="/change-password" className="action-btn secondary-btn">
                Сменить пароль
              </Link>
            </div>
          </div>
          <div className="analytics-sidebar">
            <Link to="/analytics" className="analytics-link">
              <div className="analytics-preview-card">
                <div className="analytics-preview-header">
                  <h3>Аналитика обучения</h3>
                </div>
                <p className="analytics-preview-text">
                  Посмотрите подробную статистику вашего прогресса
                </p>
                <div className="analytics-stats-preview">
                  <div className="preview-stat">
                    <div className="preview-stat-value">{progressDisplay}</div>
                    <div className="preview-stat-label">Общий прогресс</div>
                  </div>
                  <div className="preview-stat">
                    <div className="preview-stat-value">{materialsDisplay}</div>
                    <div className="preview-stat-label">Материалы</div>
                  </div>
                  <div className="preview-stat">
                    <div className="preview-stat-value">{testsDisplay}</div>
                    <div className="preview-stat-label">Тесты</div>
                  </div>
                </div>
                <div className="view-analytics-btn">Подробная аналитика</div>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PersonalAccount;
