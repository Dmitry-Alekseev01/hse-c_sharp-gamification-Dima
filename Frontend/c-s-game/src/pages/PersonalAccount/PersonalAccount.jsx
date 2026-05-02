import React from 'react';
import { Link } from 'react-router-dom';
import { useProfileStats } from '../../hooks/useProfile';
import './PersonalAccount.css';

const PersonalAccount = () => {
  const { profile, stats, isLoading, error } = useProfileStats();

  if (isLoading) return <div className="loading">Загрузка профиля...</div>;
  if (error) return <div className="error">Ошибка: {error.message}</div>;
  if (!profile) return <div className="error">Пожалуйста, войдите в систему</div>;

  const getRegistrationDate = (profile) => {
    const dateString = profile.created_at || profile.registered_at || profile.date_joined;
    if (!dateString) return null;
    const date = new Date(dateString);
    return isNaN(date)
      ? null
      : date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
  };

  let displayName = profile.full_name;
  if (!displayName)
    displayName =
      profile.username && profile.username.includes('@') ? 'Пользователь' : profile.username;
  const registrationDate = getRegistrationDate(profile);

  const materialsDisplay = `0/${stats.totalMaterials || 0}`;
  const testsDisplay = `${stats.completedTests || 0}/${stats.totalTests || 0}`;
  const progressDisplay = `${stats.overallProgress || 0}%`;

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
                  <span className="login-value">@{profile.username}</span>
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
