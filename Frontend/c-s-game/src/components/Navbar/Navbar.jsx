import React, { useState, useRef, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { PERSONAL_ACCOUNT_ROUTE } from '../../routing/const';
import { getToken, logoutUser, fetchUserProfile } from '../../api/api';
import { useQuery } from '@tanstack/react-query';
import './Navbar.css';

const Navbar = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const location = useLocation();
  const menuRef = useRef(null);

  const { data: profile } = useQuery({
    queryKey: ['userProfile'],
    queryFn: fetchUserProfile,
    enabled: !!getToken(),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsProfileMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const userName = profile ? profile.full_name || profile.username : '';

  const NAV_ITEMS = [
    { path: '/', label: 'Главная' },
    { path: '/materials', label: 'Материалы' },
    { path: '/tests', label: 'Тесты' },
    { path: PERSONAL_ACCOUNT_ROUTE, label: 'Личный кабинет' },
  ];

  return (
    <nav className="Navbar">
      <div className="nav-container">
        <NavLink to="/" className="nav-brand">
          <img src="/logo-c-sharp.png" alt="C#-мастер" className="nav-logo" />
          {/* <span>C#-мастер</span> */}
        </NavLink>

        <button className="mobile-menu-btn" onClick={() => setIsMenuOpen(!isMenuOpen)}>
          {isMenuOpen ? '✕' : '☰'}
        </button>

        <div className={`nav-links ${isMenuOpen ? 'open' : ''}`}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
              onClick={() => setIsMenuOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
        </div>

        <div className="nav-user">
          {getToken() ? (
            <div className="profile-container" ref={menuRef}>
              <div
                className="profile-trigger"
                onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
              >
                <div className="user-avatar">
                  {userName ? userName.charAt(0).toUpperCase() : '?'}
                </div>
                <span className="user-name">{userName || 'Профиль'}</span>
              </div>
              {isProfileMenuOpen && (
                <div className="profile-dropdown">
                  <NavLink
                    to={PERSONAL_ACCOUNT_ROUTE}
                    className="dropdown-item"
                    onClick={() => setIsProfileMenuOpen(false)}
                  >
                    Личный кабинет
                  </NavLink>
                  <button className="dropdown-item" onClick={logoutUser}>
                    Выйти
                  </button>
                </div>
              )}
            </div>
          ) : (
            <NavLink to="/login" className="login-btn">
              Войти
            </NavLink>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
