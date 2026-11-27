import { expect, test, type Browser, type Page } from '@playwright/test';

// Regenerates the README screenshots: SCREENSHOTS=1 pnpm e2e screenshots
test.skip(!process.env.SCREENSHOTS, 'Set SCREENSHOTS=1 to regenerate the README images.');

const out = (name: string) => `../docs/images/${name}.png`;

async function open(browser: Browser, name: string): Promise<Page> {
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 900 } })).newPage();
  page.on('dialog', (d) => d.accept());
  await page.goto('/');
  if (name) {
    await page.getByRole('button', { name: new RegExp(name) }).click();
    await expect(page.getByRole('heading', { name: 'Assembleia de demonstração' })).toBeVisible();
  }
  return page;
}

test('README screenshots', async ({ browser }) => {
  const visitor = await open(browser, '');
  await visitor.screenshot({ path: out('sign-in') });
  const chair = await open(browser, 'Ana Presidente');
  const member = await open(browser, 'Diego Associado');
  for (const page of [chair, member]) {
    await page.getByRole('button', { name: 'Confirmar presença de teste' }).click();
    await expect(page.locator('.presence-label')).toHaveText('Registrada');
  }
  await chair.getByRole('button', { name: 'Instalar em segunda convocação' }).click();
  const item = chair.locator('.agenda article').filter({ hasText: 'Eleição da diretoria' });
  await item.getByRole('button', { name: 'Abrir votação' }).click();
  await expect(member.getByRole('button', { name: 'Chapa 1 — Continuidade' })).toBeVisible({ timeout: 10_000 });
  await member.locator('.ballot-panel').screenshot({ path: out('secret-election-ballot') });
  for (const page of [member, chair]) {
    await page.getByRole('button', { name: 'Chapa 1 — Continuidade' }).click();
    await page.getByRole('button', { name: 'Confirmar voto' }).click();
  }
  await chair.getByRole('button', { name: 'Encerrar votação' }).click();
  await expect(chair.locator('.result')).toContainText('Eleita');
  await chair.screenshot({ path: out('assembly'), fullPage: true });
  await chair.getByRole('button', { name: 'Administração' }).click();
  await expect(chair.getByRole('heading', { name: 'Associados', exact: true })).toBeVisible();
  await chair.screenshot({ path: out('administration') });
});
