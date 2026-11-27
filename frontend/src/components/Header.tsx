import type { View } from '../App';
import { useI18n, type Language, type MessageKey } from '../i18n';
import type { Me } from '../types';

interface Props {
  me: Me | null;
  view: View;
  setView: (view: View) => void;
  onSignOut: () => void;
  busy: boolean;
}

export function Header({ me, view, setView, onSignOut, busy }: Props) {
  const { t, lang, setLang } = useI18n();
  const tabs: View[] = me?.is_admin ? ['assembly', 'admin', 'privacy'] : ['assembly', 'privacy'];
  return (
    <header>
      <div className="brand">
        <span className="monogram">V</span>
        <div>
          <strong>Votria</strong>
          <small>{t('brand.tagline')}</small>
        </div>
      </div>
      <nav aria-label="Votria">
        {tabs.map((tab) => (
          <button
            key={tab}
            className={'nav-tab' + (view === tab ? ' active' : '')}
            aria-current={view === tab ? 'page' : undefined}
            onClick={() => setView(tab)}
          >
            {t(`nav.${tab}` as MessageKey)}
          </button>
        ))}
        <label className="lang">
          <span className="visually-hidden">{t('language')}</span>
          <select value={lang} onChange={(e) => setLang(e.target.value as Language)} aria-label={t('language')}>
            <option value="pt">PT</option>
            <option value="en">EN</option>
          </select>
        </label>
        {me && (
          <button className="nav-tab" disabled={busy} onClick={onSignOut}>
            {t('header.signOut')}
          </button>
        )}
      </nav>
    </header>
  );
}
