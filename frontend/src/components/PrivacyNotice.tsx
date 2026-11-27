import { useI18n } from '../i18n';

export function PrivacyNotice({ organization }: { organization: string }) {
  const { t } = useI18n();
  return (
    <main className="workspace narrow">
      <section className="card">
        <h1>{t('privacy.title')}</h1>
        <p>{t('privacy.controller', { org: organization })}</p>
        <p>{t('privacy.data')}</p>
        <p>{t('privacy.purpose')}</p>
        <p>{t('privacy.retention')}</p>
        <p>{t('privacy.rights', { org: organization })}</p>
        <p className="muted">{t('privacy.note')}</p>
      </section>
    </main>
  );
}
