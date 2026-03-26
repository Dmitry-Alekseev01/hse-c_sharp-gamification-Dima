import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './ChangePassword.css';

const ChangePassword = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.currentPassword) {
      newErrors.currentPassword = 'Введите текущий пароль';
    }

    if (!formData.newPassword) {
      newErrors.newPassword = 'Введите новый пароль';
    } else if (formData.newPassword.length < 6) {
      newErrors.newPassword = 'Пароль должен содержать минимум 6 символов';
    }

    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Подтвердите новый пароль';
    } else if (formData.newPassword !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Пароли не совпадают';
    }

    if (formData.currentPassword && formData.currentPassword !== 'oldpassword') {
      newErrors.currentPassword = 'Неверный текущий пароль';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSuccessMessage('');

    if (!validateForm()) return;

    setIsLoading(true);

    setTimeout(() => {
      setIsLoading(false);
      setSuccessMessage('Пароль успешно изменён!');
      setFormData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      });
      setTimeout(() => {
        navigate('/personal-account');
      }, 2000);
    }, 1500);
  };

  return (
    <div className="change-password-container">
      <div className="change-password-card">
        <h1>Смена пароля</h1>
        <p>Введите текущий пароль и новый пароль для смены.</p>

        <form onSubmit={handleSubmit} className="change-password-form">
          <div className="form-group">
            <label htmlFor="currentPassword">Текущий пароль</label>
            <input
              type="password"
              id="currentPassword"
              name="currentPassword"
              value={formData.currentPassword}
              onChange={handleChange}
              placeholder="Введите текущий пароль"
              className={errors.currentPassword ? 'error' : ''}
            />
            {errors.currentPassword && <span className="error-text">{errors.currentPassword}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="newPassword">Новый пароль</label>
            <input
              type="password"
              id="newPassword"
              name="newPassword"
              value={formData.newPassword}
              onChange={handleChange}
              placeholder="Введите новый пароль"
              className={errors.newPassword ? 'error' : ''}
            />
            {errors.newPassword && <span className="error-text">{errors.newPassword}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Подтверждение нового пароля</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="Повторите новый пароль"
              className={errors.confirmPassword ? 'error' : ''}
            />
            {errors.confirmPassword && <span className="error-text">{errors.confirmPassword}</span>}
          </div>

          {successMessage && <div className="success-message">{successMessage}</div>}

          <div className="form-actions">
            <button type="submit" className="submit-btn" disabled={isLoading}>
              {isLoading ? 'Сохранение...' : 'Сменить пароль'}
            </button>
            <Link to="/personal-account" className="cancel-btn">
              Отмена
            </Link>
          </div>
        </form>

        <div className="auth-note">
          <p>
            Для демонстрации используйте текущий пароль: <strong>oldpassword</strong>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChangePassword;
