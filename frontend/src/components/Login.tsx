import { useState } from 'react';
import { useI18n } from '../i18n';
import type { Config, DemoAccount } from '../types';

interface Props {
  config: Config;
  busy: boolean;
  onChoose: (memberId: string, password: string) => void;
}

export function Login({ config, busy, onChoose }: Props) {
  const { t } = useI18n();
  const [password, setPassword] = useState('');
  const groups = config.demo_accounts.reduce<Record<string, DemoAccount[]>>((acc, account) => {
    (acc[account.organization] ??= []).push(account);
    return acc;
  }, {});
  return (
    <main className="login-layout">
      <section>
        <p className="eyebrow">{config.institution_name ? config.institution_name.toUpperCase() : t('login.eyebrow')}</p>
        <h1>{t('login.title')}</h1>
        <p className="intro">{t('login.intro')}</p>
        {(['login.f1', 'login.f2', 'login.f3'] as const).map((key, i) => (
          <div className="login-feature" key={key}>
            <span>0{i + 1}</span> {t(key)}
          </div>
        ))}
      </section>
      <section className="card login-card">
        <p className="eyebrow">{t('login.access')}</p>
        <h2>{t('login.heading')}</h2>
        <p>
          {config.institutional_domain
            ? t('login.requires', { domain: '@' + config.institutional_domain })
            : t('login.requiresGeneric')}
        </p>
        <a
          className={'button primary' + (config.oidc_configured ? '' : ' disabled')}
          href={config.oidc_configured ? '/auth/login' : undefined}
          aria-disabled={!config.oidc_configured}
        >
          {t('login.institutional')}
        </a>
        {!config.oidc_configured && <p className="muted">{t('login.pending')}</p>}
        <hr />
        {config.demo && (
          <>
            <h3>{t('login.demoTitle')}</h3>
            <p className="muted">{t('login.demoHelp')}</p>
            {config.demo_password_required && (
              <>
                <label htmlFor="demo-access-password">{t('login.password')}</label>
                <input
                  id="demo-access-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t('login.passwordPlaceholder')}
                />
              </>
            )}
            {Object.entries(groups).map(([organization, accounts]) => (
              <div key={organization} className="demo-group">
                {Object.keys(groups).length > 1 && <p className="eyebrow">{organization}</p>}
                <div className="demo-users">
                  {accounts.map((m) => (
                    <button disabled={busy} key={m.id} onClick={() => onChoose(m.id, password)}>
                      <span>{m.name}</span>
                      <small>{m.email}</small>
                      <span className="arrow" aria-hidden="true">
                        →
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </>
        )}
      </section>
    </main>
  );
}
