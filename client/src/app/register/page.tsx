'use client';

import Link from 'next/link';
import styles from '../auth.module.css';
import { useState } from 'react';

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className={styles.container}>
      <div className={styles.leftSide}>
        <div className={styles.leftSideOverlay} />
        <div className={styles.leftSideContent}>
          <div className={styles.header}>
            <div className={styles.logo}>AMU</div>
            <Link href="/" className={styles.backLink}>
              Back to website <span>→</span>
            </Link>
          </div>
          
          <div className={styles.testimonial}>
            <h2 className={styles.testimonialText}>
              Capturing Moments,<br />Creating Memories
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
          <h1 className={styles.title}>Create an account</h1>
          <p className={styles.subtitle}>
            Already have an account? <Link href="/login" className={styles.link}>Log in</Link>
          </p>

          <form onSubmit={(e) => e.preventDefault()}>
            <div className={styles.formGroupRow}>
              <div className={styles.formGroup}>
                <input type="text" placeholder="First Name" className={styles.input} />
              </div>
              <div className={styles.formGroup}>
                <input type="text" placeholder="Last Name" className={styles.input} />
              </div>
            </div>

            <div className={styles.formGroup}>
              <input type="email" placeholder="Email" className={styles.input} />
            </div>

            <div className={styles.formGroup}>
              <input 
                type={showPassword ? "text" : "password"} 
                placeholder="Enter your password" 
                className={styles.input} 
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

            <div className={styles.checkboxGroup}>
              <input type="checkbox" id="terms" className={styles.checkbox} defaultChecked />
              <label htmlFor="terms">
                I agree to the <Link href="/terms">Terms & Conditions</Link>
              </label>
            </div>

            <button type="submit" className={styles.submitBtn}>
              Create account
            </button>
          </form>

          <div className={styles.divider}>Or register with</div>

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
