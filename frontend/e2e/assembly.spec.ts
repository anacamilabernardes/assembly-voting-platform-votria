import { expect, test, type Browser, type Page } from '@playwright/test';

const consoleErrors: string[] = [];

async function signIn(browser: Browser, name: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on('dialog', (dialog) => dialog.accept());
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource')) consoleErrors.push(message.text());
  });
  page.on('response', (response) => {
    if (response.status() >= 400) consoleErrors.push(`${response.status()} ${response.request().method()} ${response.url()}`);
  });
  await page.goto('/');
  await page.getByRole('button', { name: new RegExp(name) }).click();
  await expect(page.getByRole('heading', { name: 'Assembleia de demonstração' })).toBeVisible();
  return page;
}

async function confirmPresence(page: Page) {
  await page.getByRole('button', { name: 'Confirmar presença de teste' }).click();
  await expect(page.locator('.presence-label')).toHaveText('Registrada');
}

async function vote(page: Page, choice: string) {
  await page.locator('.ballot-card').first().getByRole('button', { name: choice, exact: true }).click();
  await page.getByRole('button', { name: 'Confirmar voto' }).click();
  await expect(page.getByRole('status')).toContainText('Voto confirmado');
}

function agendaItem(page: Page, title: string) {
  return page.locator('.agenda article').filter({ hasText: title });
}

test.describe.serial('assembly flow', () => {
  let chair: Page;
  let member: Page;

  test.beforeAll(async ({ browser }) => {
    chair = await signIn(browser, 'Ana Presidente');
    member = await signIn(browser, 'Carla Associada');
  });

  test('chair installs the assembly and runs a roll-call vote', async () => {
    await confirmPresence(chair);
    await chair.getByRole('button', { name: 'Instalar em segunda convocação' }).click();
    await expect(chair.getByText('Trabalhos instalados')).toBeVisible();
    await agendaItem(chair, 'Aprovação do plano de atividades').getByRole('button', { name: 'Abrir votação' }).click();
    await vote(chair, 'SIM');
    await chair.getByRole('button', { name: 'Encerrar votação' }).click();
    await expect(chair.locator('.result')).toContainText('Proposta aprovada');
    await expect(chair.locator('.table-wrap')).toContainText('SIM');
  });

  test('secret ballot shows who voted but never the choices', async () => {
    await confirmPresence(member);
    await agendaItem(chair, 'Reajuste da contribuição anual').getByRole('button', { name: 'Abrir votação' }).click();
    await expect(member.getByText('Voto secreto: o sistema registra')).toBeVisible({ timeout: 10_000 });
    await vote(member, 'NÃO');
    await expect(member.locator('.receipt')).toContainText('Voto secreto registrado');
    await vote(chair, 'SIM');
    await chair.getByRole('button', { name: 'Encerrar votação' }).click();
    await expect(chair.locator('.result')).toContainText('1 SIM');
    await expect(chair.locator('.result')).toContainText('1 NÃO');
    const table = chair.locator('.table-wrap');
    await expect(table).toContainText('Votaram (sem registro da escolha)');
    await expect(table).toContainText('Carla Associada');
    await expect(table).not.toContainText('NÃO');
  });

  test('election with slates elects the most voted option', async () => {
    await agendaItem(chair, 'Eleição da diretoria').getByRole('button', { name: 'Abrir votação' }).click();
    await expect(member.getByRole('button', { name: 'Chapa 2 — Renovação' })).toBeVisible({ timeout: 10_000 });
    await vote(member, 'Chapa 2 — Renovação');
    await vote(chair, 'Chapa 2 — Renovação');
    await chair.getByRole('button', { name: 'Encerrar votação' }).click();
    await expect(chair.locator('.result')).toContainText('Eleita: Chapa 2 — Renovação');
  });

  test('closing produces printable minutes', async () => {
    await chair.getByRole('button', { name: 'Finalizar assembleia' }).click();
    const [minutes] = await Promise.all([
      chair.context().waitForEvent('page'),
      chair.getByRole('link', { name: /Abrir minuta/ }).click(),
    ]);
    await expect(minutes.getByRole('heading', { name: 'Deliberações' })).toBeVisible();
    await expect(minutes.locator('body')).toContainText('Eleição da diretoria');
    await expect(minutes.locator('body')).toContainText('Eleita — Chapa 2 — Renovação');
  });

  test('administrator builds and publishes a new assembly', async () => {
    await chair.getByRole('button', { name: 'Administração' }).click();
    await chair.getByLabel('Título', { exact: true }).fill('Assembleia extraordinária');
    await chair.getByLabel('Presidência').selectOption({ label: 'Ana Presidente' });
    await chair.getByLabel('Secretaria').selectOption({ label: 'Bruno Secretário' });
    await chair.getByRole('button', { name: 'Criar rascunho' }).click();
    await expect(chair.getByText('Rascunho criado')).toBeVisible();
    await chair.getByLabel('Título da pauta').fill('Eleição do conselho fiscal');
    await chair.getByLabel('Texto da proposta').fill('Eleger o conselho fiscal para o próximo mandato.');
    await chair.getByLabel('Tipo').selectOption('ELECTION');
    await chair.getByLabel('Candidaturas ou chapas').fill('Chapa Azul\nChapa Verde');
    await chair.getByRole('button', { name: 'Incluir pauta' }).last().click();
    await expect(chair.getByText('Pauta incluída')).toBeVisible();
    await chair.getByRole('button', { name: 'Publicar assembleia' }).click();
    await expect(chair.getByText('Assembleia publicada para 7 associados')).toBeVisible();
    await chair.getByRole('button', { name: 'Assembleia', exact: true }).click();
    const option = chair.locator('#assembly-switch option', { hasText: 'Assembleia extraordinária' });
    await chair.locator('#assembly-switch').selectOption((await option.getAttribute('value'))!);
    await expect(chair.getByRole('heading', { name: 'Assembleia extraordinária' })).toBeVisible();
  });

  test('interface switches to English without reloading', async () => {
    await member.getByLabel('Idioma').selectOption('en');
    await expect(member.getByRole('heading', { name: 'Agenda' })).toBeVisible();
  });

  test('no console errors or content-security-policy violations', async () => {
    expect(consoleErrors).toEqual([]);
  });
});
