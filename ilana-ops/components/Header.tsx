'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';

interface HeaderProps {
  onLogout: () => void;
}

export default function Header({ onLogout }: HeaderProps) {
  const pathname = usePathname();

  const navItems = [
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/analytics', label: 'Analytics' },
    { href: '/activity', label: 'Activity' },
  ];

  return (
    <header className="header" role="banner">
      <div className="container header-content">
        <div className="header-left">
          <Link href="/dashboard" className="logo" aria-label="Ilana Ops Portal">
            ILANA <span>Ops</span>
          </Link>
          <nav className="header-nav" aria-label="Main navigation">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link ${pathname === item.href ? 'nav-link-active' : ''}`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
        <button
          className="btn btn-outline"
          onClick={onLogout}
          aria-label="Log out of ops portal"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
