import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { LaboratoryPanel } from '../LaboratoryPanel';
it('shows the original comparison sign, unknown reference and review boundary', () => {
  render(<LaboratoryPanel version={2} pages={[{ pageNumber: 3 }]} lab={{ candidateRows: 2, dates: [{ role: 'SPECIMEN', raw: '17.06.2026' }], issues: [{ code: 'UNSUPPORTED_ROW' }], rows: [{ name: 'Ферритин', result: { raw: '<5,0' }, unit: 'мкг/л', referenceRaw: null, subject: 'UNKNOWN', sourceText: 'Ферритин <5,0 мкг/л', source: { pageIndex: 0 } }] }} />);
  expect(screen.getByText('<5,0')).toBeVisible();
  expect(screen.getByText('Не указан')).toBeVisible();
  expect(screen.getByText(/ваши исправления и подтверждения/)).toBeVisible();
  expect(screen.getByText(/Требуют проверки: 1/)).toBeVisible();
  expect(screen.getByText('Дата взятия материала: 17.06.2026')).toBeVisible();
});
