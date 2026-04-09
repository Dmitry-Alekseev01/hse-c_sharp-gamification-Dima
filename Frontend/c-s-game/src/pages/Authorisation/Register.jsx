// import React, { useState } from 'react';
// import { Link, useNavigate } from 'react-router-dom';
// import { MAIN_ROUTE, LOGIN_ROUTE } from '../../routing/const';
// import './Authorisation.css';

// const Register = () => {
//   const [formData, setFormData] = useState({
//     name: '',
//     email: '',
//     password: '',
//     confirmPassword: '',
//     agreeTerms: false,
//   });
//   const [errors, setErrors] = useState({});
//   const [isLoading, setIsLoading] = useState(false);
//   const navigate = useNavigate();

//   const handleChange = (e) => {
//     const { name, value, type, checked } = e.target;
//     setFormData((prev) => ({
//       ...prev,
//       [name]: type === 'checkbox' ? checked : value,
//     }));

//     if (errors[name]) {
//       setErrors((prev) => ({
//         ...prev,
//         [name]: '',
//       }));
//     }
//   };

//   const validateForm = () => {
//     const newErrors = {};

//     if (!formData.name.trim()) {
//       newErrors.name = 'Введите имя';
//     } else if (formData.name.length < 2) {
//       newErrors.name = 'Имя должно содержать минимум 2 символа';
//     }

//     if (!formData.email) {
//       newErrors.email = 'Введите email';
//     } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
//       newErrors.email = 'Введите корректный email';
//     }

//     if (!formData.password) {
//       newErrors.password = 'Введите пароль';
//     } else if (formData.password.length < 6) {
//       newErrors.password = 'Пароль должен содержать минимум 6 символов';
//     }

//     if (!formData.confirmPassword) {
//       newErrors.confirmPassword = 'Подтвердите пароль';
//     } else if (formData.password !== formData.confirmPassword) {
//       newErrors.confirmPassword = 'Пароли не совпадают';
//     }

//     if (!formData.agreeTerms) {
//       newErrors.agreeTerms = 'Необходимо согласиться с условиями';
//     }

//     setErrors(newErrors);
//     return Object.keys(newErrors).length === 0;
//   };

//   const handleSubmit = async (e) => {
//     e.preventDefault();

//     if (!validateForm()) {
//       return;
//     }

//     setIsLoading(true);

//     try {
//       await new Promise((resolve) => setTimeout(resolve, 1500));

//       localStorage.setItem('isAuthenticated', 'true');
//       localStorage.setItem('userEmail', formData.email);
//       localStorage.setItem('userName', formData.name);

//       navigate(MAIN_ROUTE);
//     } catch (error) {
//       console.error('Ошибка регистрации:', error);
//       setErrors((prev) => ({
//         ...prev,
//         submit: 'Ошибка регистрации. Попробуйте снова.',
//       }));
//     } finally {
//       setIsLoading(false);
//     }
//   };

//   return (
//     <div className="auth-container">
//       <div className="auth-card">
//         <div className="auth-header">
//           <h1>Регистрация</h1>
//           <p>Создайте новый аккаунт для доступа к платформе</p>
//         </div>

//         <form onSubmit={handleSubmit} className="auth-form">
//           <div className="form-group">
//             <label htmlFor="name">Имя</label>
//             <input
//               type="text"
//               id="name"
//               name="name"
//               value={formData.name}
//               onChange={handleChange}
//               placeholder="Введите ваше имя"
//               className={errors.name ? 'error' : ''}
//             />
//             {errors.name && <span className="error-text">{errors.name}</span>}
//           </div>

//           <div className="form-group">
//             <label htmlFor="email">Email</label>
//             <input
//               type="email"
//               id="email"
//               name="email"
//               value={formData.email}
//               onChange={handleChange}
//               placeholder="Введите ваш email"
//               className={errors.email ? 'error' : ''}
//             />
//             {errors.email && <span className="error-text">{errors.email}</span>}
//           </div>

//           <div className="form-group">
//             <label htmlFor="password">Пароль</label>
//             <input
//               type="password"
//               id="password"
//               name="password"
//               value={formData.password}
//               onChange={handleChange}
//               placeholder="Придумайте пароль"
//               className={errors.password ? 'error' : ''}
//             />
//             {errors.password && <span className="error-text">{errors.password}</span>}
//           </div>

//           <div className="form-group">
//             <label htmlFor="confirmPassword">Подтверждение пароля</label>
//             <input
//               type="password"
//               id="confirmPassword"
//               name="confirmPassword"
//               value={formData.confirmPassword}
//               onChange={handleChange}
//               placeholder="Повторите пароль"
//               className={errors.confirmPassword ? 'error' : ''}
//             />
//             {errors.confirmPassword && <span className="error-text">{errors.confirmPassword}</span>}
//           </div>

//           <div className="form-group checkbox-group">
//             <input
//               type="checkbox"
//               id="agreeTerms"
//               name="agreeTerms"
//               checked={formData.agreeTerms}
//               onChange={handleChange}
//               className={errors.agreeTerms ? 'error' : ''}
//             />
//             <label htmlFor="agreeTerms">
//               Я согласен с <Link to="/terms">Условиями использования</Link> и{' '}
//               <Link to="/privacy">Политикой конфиденциальности</Link>
//             </label>
//             {errors.agreeTerms && <span className="error-text">{errors.agreeTerms}</span>}
//           </div>

//           {errors.submit && <div className="submit-error">{errors.submit}</div>}

//           <button type="submit" className="auth-button" disabled={isLoading}>
//             {isLoading ? 'Регистрация...' : 'Зарегистрироваться'}
//           </button>
//         </form>

//         <div className="auth-switch">
//           <p>
//             Уже есть аккаунт?{' '}
//             <Link to={LOGIN_ROUTE} className="switch-link">
//               Войти
//             </Link>
//           </p>
//         </div>
//       </div>
//     </div>
//   );
// };

// export default Register;

import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { registerUser } from '../../api/api';
import { MAIN_ROUTE, LOGIN_ROUTE } from '../../routing/const';
import './Authorisation.css';

const Register = () => {
  const [formData, setFormData] = useState({
    username: '',
    fullName: '',
    password: '',
    confirmPassword: '',
    agreeTerms: false,
  });
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
    if (!formData.username.trim()) newErrors.username = 'Введите имя пользователя';
    else if (formData.username.length < 3) newErrors.username = 'Минимум 3 символа';
    if (!formData.fullName.trim()) newErrors.fullName = 'Введите имя';
    if (!formData.password) newErrors.password = 'Введите пароль';
    else if (formData.password.length < 6)
      newErrors.password = 'Пароль должен быть не менее 6 символов';
    if (formData.password !== formData.confirmPassword)
      newErrors.confirmPassword = 'Пароли не совпадают';
    if (!formData.agreeTerms) newErrors.agreeTerms = 'Необходимо согласиться с условиями';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setIsLoading(true);
    try {
      await registerUser(formData.username, formData.password, formData.fullName);
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
          <h1>Регистрация</h1>
          <p>Создайте новый аккаунт</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label>Имя пользователя</label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="Придумайте имя пользователя"
              className={errors.username ? 'error' : ''}
            />
            {errors.username && <span className="error-text">{errors.username}</span>}
          </div>
          <div className="form-group">
            <label>Ваше имя</label>
            <input
              type="text"
              name="fullName"
              value={formData.fullName}
              onChange={handleChange}
              placeholder="Как к вам обращаться"
              className={errors.fullName ? 'error' : ''}
            />
            {errors.fullName && <span className="error-text">{errors.fullName}</span>}
          </div>
          <div className="form-group">
            <label>Пароль</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Придумайте пароль"
              className={errors.password ? 'error' : ''}
            />
            {errors.password && <span className="error-text">{errors.password}</span>}
          </div>
          <div className="form-group">
            <label>Подтверждение пароля</label>
            <input
              type="password"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="Повторите пароль"
              className={errors.confirmPassword ? 'error' : ''}
            />
            {errors.confirmPassword && <span className="error-text">{errors.confirmPassword}</span>}
          </div>
          <div className="form-group checkbox-group">
            <input
              type="checkbox"
              name="agreeTerms"
              checked={formData.agreeTerms}
              onChange={handleChange}
            />
            <label>
              Я согласен с <Link to="/terms">Условиями использования</Link>
            </label>
            {errors.agreeTerms && <span className="error-text">{errors.agreeTerms}</span>}
          </div>
          {errors.submit && <div className="submit-error">{errors.submit}</div>}
          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? 'Регистрация...' : 'Зарегистрироваться'}
          </button>
        </form>
        <div className="auth-switch">
          <p>
            Уже есть аккаунт?{' '}
            <Link to={LOGIN_ROUTE} className="switch-link">
              Войти
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;
