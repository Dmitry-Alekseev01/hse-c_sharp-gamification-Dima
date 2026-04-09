// import React, { useState, useRef, useEffect } from 'react';
// import { NavLink, useLocation } from 'react-router-dom';
// import {
//   MAIN_ROUTE,
//   MATERIALS_ROUTE,
//   TESTS_ROUTE,
//   PERSONAL_ACCOUNT_ROUTE,
// } from '../../routing/const';
// import { isAuthenticated, logout } from '../../pages/Authorisation/auth';
// import './Navbar.css';

// const Navbar = () => {
//   const [isMenuOpen, setIsMenuOpen] = useState(false);
//   const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
//   const location = useLocation();
//   const menuRef = useRef(null);

//   const NAV_ITEMS = [
//     { path: MAIN_ROUTE, label: 'Главная' },
//     { path: MATERIALS_ROUTE, label: 'Материалы' },
//     { path: TESTS_ROUTE, label: 'Тесты' },
//     { path: PERSONAL_ACCOUNT_ROUTE, label: 'Личный кабинет' },
//   ];

//   const toggleMenu = () => {
//     setIsMenuOpen(!isMenuOpen);
//   };

//   const isActive = (path) => {
//     return location.pathname === path;
//   };

//   const userName = localStorage.getItem('userName') || 'Пользователь';
//   const userAvatar = userName.charAt(0).toUpperCase();

//   useEffect(() => {
//     const handleClickOutside = (event) => {
//       if (menuRef.current && !menuRef.current.contains(event.target)) {
//         setIsProfileMenuOpen(false);
//       }
//     };
//     document.addEventListener('mousedown', handleClickOutside);
//     return () => document.removeEventListener('mousedown', handleClickOutside);
//   }, []);

//   return (
//     <nav className="Navbar">
//       <div className="nav-container">
//         <NavLink to="/" className="nav-brand">
//           <div className="bank-logo">Т</div>
//           <span>Т-Образование</span>
//         </NavLink>

//         <button className="mobile-menu-btn" onClick={toggleMenu}>
//           {isMenuOpen ? '✕' : '☰'}
//         </button>

//         <div className={`nav-links ${isMenuOpen ? 'open' : ''}`}>
//           {NAV_ITEMS.map((item) => (
//             <NavLink
//               key={item.path}
//               to={item.path}
//               className={`nav-link ${isActive(item.path) ? 'active' : ''}`}
//               onClick={() => setIsMenuOpen(false)}
//             >
//               {item.label}
//             </NavLink>
//           ))}
//         </div>

//         <div className="nav-user">
//           {isAuthenticated() ? (
//             <div className="profile-container" ref={menuRef}>
//               <div
//                 className="profile-trigger"
//                 onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
//               >
//                 <div className="user-avatar">{userAvatar}</div>
//                 <span className="user-name">{userName}</span>
//               </div>
//               {isProfileMenuOpen && (
//                 <div className="profile-dropdown">
//                   <NavLink
//                     to={PERSONAL_ACCOUNT_ROUTE}
//                     className="dropdown-item"
//                     onClick={() => setIsProfileMenuOpen(false)}
//                   >
//                     Личный кабинет
//                   </NavLink>
//                   <button className="dropdown-item" onClick={logout}>
//                     Выйти
//                   </button>
//                 </div>
//               )}
//             </div>
//           ) : (
//             <NavLink to="/login" className="login-btn">
//               Войти
//             </NavLink>
//           )}
//         </div>
//       </div>
//     </nav>
//   );
// };

// export default Navbar;

import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { PERSONAL_ACCOUNT_ROUTE } from '../../routing/const';
import { getToken, logoutUser, fetchUserProfile } from '../../api/api';
import './Navbar.css';

const Navbar = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [userName, setUserName] = useState('');
  const location = useLocation();

  useEffect(() => {
    if (getToken()) {
      fetchUserProfile()
        .then((profile) => {
          setUserName(profile.full_name || profile.username);
        })
        .catch(() => {});
    }
  }, []);

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
          <div className="bank-logo">Т</div>
          <span>Т-Образование</span>
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
            <>
              <NavLink to={PERSONAL_ACCOUNT_ROUTE} className="user-profile-link">
                <div className="user-avatar">{userName.charAt(0).toUpperCase()}</div>
                <span className="user-name">{userName}</span>
              </NavLink>
              <button onClick={logoutUser} className="logout-btn">
                Выйти
              </button>
            </>
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
