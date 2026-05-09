import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchLearningDashboard, fetchUserProfile } from '../../api/api';
import './PersonalAccount.css';

const PersonalAccount = () => {
  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['userProfile'],
    queryFn: fetchUserProfile,
  });

  const { data: dashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ['learningDashboard'],
    queryFn: () => fetchLearningDashboard(200),
  });

  const isLoading = profileLoading || dashboardLoading;

  if (isLoading) return <div className="loading">Загрузка профиля...</div>;
  if (!profile) return <div className="error">Пожалуйста, войдите в систему</div>;

  const formatDate = (dateString) => {
    if (!dateString) return 'Не указана';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'Не указана';
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  const displayName = profile.full_name || profile.username || 'Пользователь';
  const registrationDate =
    formatDate(profile.created_at) || formatDate(profile.registered_at) || 'Не указана';

  const stats = {
    totalMaterials: dashboard?.total_materials || 0,
    completedTests: dashboard?.completed_tests || 0,
    totalTests: dashboard?.total_tests || 0,
    overallProgress: dashboard?.total_tests
      ? Math.round((dashboard.completed_tests / dashboard.total_tests) * 100)
      : 0,
  };

  return (
    <div className="personal-account-page">
      {/* ... (заголовок) ... */}
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
                  <span className="login-value">@{profile.username}</span>
                </div>
              </div>
              <div className="detail-item">
                <div className="detail-label">Дата регистрации:</div>
                <div className="detail-value">
                  <span className="date-value">{registrationDate}</span>
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
                    <div className="preview-stat-value">{stats.overallProgress}%</div>
                    <div className="preview-stat-label">Общий прогресс</div>
                  </div>
                  <div className="preview-stat">
                    <div className="preview-stat-value">{stats.totalMaterials}</div>
                    <div className="preview-stat-label">Материалы</div>
                  </div>
                  <div className="preview-stat">
                    <div className="preview-stat-value">
                      {stats.completedTests}/{stats.totalTests}
                    </div>
                    <div className="preview-stat-label">Тесты</div>
                  </div>
                </div>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PersonalAccount;
