import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { loginUser } from '../../api/api';
import { MAIN_ROUTE, REGISTER_ROUTE, FORGOT_PASSWORD_ROUTE } from '../../routing/const';
import './Authorisation.css';

const Login = () => {
  const [formData, setFormData] = useState({ username: '', password: '', rememberMe: false });
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.username) newErrors.username = 'Введите имя пользователя';
    if (!formData.password) newErrors.password = 'Введите пароль';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setIsLoading(true);
    try {
      await loginUser(formData.username, formData.password);
      if (formData.rememberMe) localStorage.setItem('rememberMe', 'true');
      navigate(MAIN_ROUTE);
    } catch (err) {
      setErrors({ submit: err.message });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>Вход в систему</h1>
          <p>Введите ваши учётные данные</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label>Email</label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="Введите ваш email"
              className={errors.username ? 'error' : ''}
            />
            {errors.username && <span className="error-text">{errors.username}</span>}
          </div>
          <div className="form-group">
            <label>Пароль</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Введите пароль"
              className={errors.password ? 'error' : ''}
            />
            {errors.password && <span className="error-text">{errors.password}</span>}
          </div>
          <div className="form-options">
            <div className="checkbox-group">
              <input
                type="checkbox"
                name="rememberMe"
                checked={formData.rememberMe}
                onChange={handleChange}
              />
              <label>Запомнить меня</label>
            </div>
            <Link to={FORGOT_PASSWORD_ROUTE} className="forgot-link">
              Забыли пароль?
            </Link>
          </div>
          {errors.submit && <div className="submit-error">{errors.submit}</div>}
          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? 'Вход...' : 'Войти'}
          </button>
        </form>
        <div className="auth-switch">
          <p>
            Нет аккаунта?{' '}
            <Link to={REGISTER_ROUTE} className="switch-link">
              Зарегистрироваться
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
