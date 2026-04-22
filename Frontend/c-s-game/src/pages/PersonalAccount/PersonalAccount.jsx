import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchUserProfile, getToken } from '../../api/api';
import './PersonalAccount.css';

const PersonalAccount = () => {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadProfile = async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const data = await fetchUserProfile();
        setProfile(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadProfile();
  }, []);

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  if (loading) return <div className="loading">Загрузка профиля...</div>;
  if (error) return <div className="error">Ошибка: {error}</div>;
  if (!profile) return <div className="error">Пожалуйста, войдите в систему</div>;

  // Отображаемое имя: сначала full_name, если нет – то username, но если username похож на email, показываем "Пользователь"
  let displayName = profile.full_name;
  if (!displayName) {
    displayName =
      profile.username && profile.username.includes('@') ? 'Пользователь' : profile.username;
  }
  const loginName = profile.username;

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
                  <span className="date-value">
                    {formatDate(profile.created_at) || 'Не указана'}
                  </span>
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
                    <div className="preview-stat-value">85%</div>
                    <div className="preview-stat-label">Общий прогресс</div>
                  </div>
                  <div className="preview-stat">
                    <div className="preview-stat-value">4/8</div>
                    <div className="preview-stat-label">Материалы</div>
                  </div>
                  <div className="preview-stat">
                    <div className="preview-stat-value">6/12</div>
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
