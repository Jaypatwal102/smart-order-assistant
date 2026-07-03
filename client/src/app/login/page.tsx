'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from '../auth.module.css';
import { useState } from 'react';
import { loginUser } from '@/utils/auth';

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const data = await loginUser(email, password);
      // Fetch user profile to get role
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/auth/me`, {
        headers: {
          Authorization: `Bearer ${data.access_token}`,
        },
      });
      if (response.ok) {
        const userData = await response.json();
        if (userData.role === 'HUMAN_AGENT') {
          router.push('/agent');
        } else {
          router.push('/support');
        }
      } else {
        router.push('/support');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.leftSide}>
        <div className={styles.leftSideOverlay} />
        <div className={styles.leftSideContent}>
          <div className={styles.header}>
            <div className={styles.logo}>SOA</div>
            <Link href="/" className={styles.backLink}>
              Back to website <span>→</span>
            </Link>
          </div>
          
          <div className={styles.testimonial}>
            <h2 className={styles.testimonialText}>
              Always happy to help
            </h2>
            <div className={styles.carouselIndicators}>
              <div className={`${styles.indicator} ${styles.active}`}></div>
              <div className={styles.indicator}></div>
              <div className={styles.indicator}></div>
            </div>
          </div>
        </div>
      </div>

      <div className={styles.rightSide}>
        <div className={styles.formContainer}>
          <h1 className={styles.title}>Welcome back</h1>
          <p className={styles.subtitle}>
            Don't have an account? <Link href="/register" className={styles.link}>Sign up</Link>
          </p>

          {error && <div style={{ color: 'red', marginBottom: '1rem', padding: '10px', backgroundColor: '#ffebee', borderRadius: '4px', fontSize: '14px' }}>{error}</div>}

          <form onSubmit={handleLogin}>
            <div className={styles.formGroup}>
              <input 
                type="email" 
                placeholder="Email" 
                className={styles.input} 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <input 
                type={showPassword ? "text" : "password"} 
                placeholder="Enter your password" 
                className={styles.input} 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <div 
                className={styles.passwordIcon}
                onClick={() => setShowPassword(!showPassword)}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  {showPassword ? (
                    <>
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </>
                  ) : (
                    <>
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                      <line x1="1" y1="1" x2="23" y2="23"></line>
                    </>
                  )}
                </svg>
              </div>
            </div>

            <div className={styles.checkboxGroup} style={{ justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <input type="checkbox" id="remember" className={styles.checkbox} />
                <label htmlFor="remember">Remember for 30 days</label>
              </div>
              <Link href="/forgot-password" style={{ color: '#a09fa5', textDecoration: 'none' }}>
                Forgot password
              </Link>
            </div>

            <button type="submit" className={styles.submitBtn} disabled={isLoading}>
              {isLoading ? 'Logging in...' : 'Log in'}
            </button>
          </form>

          <div className={styles.divider}>Or log in with</div>

          <div className={styles.socialButtons}>
            <button className={styles.socialBtn}>
              <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Google
            </button>
            <button className={styles.socialBtn}>
              <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
                <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.09 2.31-.86 3.65-.74 1.54.04 2.86.72 3.73 1.89-3.23 1.83-2.68 6.07.45 7.29-.75 1.5-1.63 2.95-2.91 3.73zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.33 2.31-1.78 4.28-3.74 4.25z"/>
              </svg>
              Apple
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
