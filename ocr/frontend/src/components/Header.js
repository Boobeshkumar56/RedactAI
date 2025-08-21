import React from 'react';
import { Link } from 'react-router-dom';
import styled from 'styled-components';

const HeaderContainer = styled.header`
  background-color: #3f51b5;
  color: white;
  padding: 1rem 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
`;

const HeaderContent = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem;
`;

const Logo = styled.h1`
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
`;

const Navigation = styled.nav`
  display: flex;
  gap: 1.5rem;
`;

const NavLink = styled(Link)`
  color: white;
  font-weight: 500;
  transition: opacity 0.3s ease;

  &:hover {
    opacity: 0.8;
  }
`;

function Header() {
  return (
    <HeaderContainer>
      <HeaderContent>
        <Link to="/">
          <Logo>RedactAI</Logo>
        </Link>
        <Navigation>
          <NavLink to="/">Upload</NavLink>
          <NavLink to="/editor">Editor</NavLink>
        </Navigation>
      </HeaderContent>
    </HeaderContainer>
  );
}

export default Header;
