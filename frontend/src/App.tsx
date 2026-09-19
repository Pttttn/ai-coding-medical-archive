import { useEffect, useState } from 'react';
import { Activity, Archive, ArrowUpRight, BookOpen, ChevronRight, Clock3, FilePlus2, HeartPulse, LayoutDashboard, Menu, MessageSquareText, Plus, ShieldCheck, X } from 'lucide-react';
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { DashboardPage } from './pages/Dashboard';
import { ArchivePage } from './pages/Archive';
import { UploadPage } from './pages/Upload';
import { DocumentPage } from './pages/Document';
import { TimelinePage } from './pages/Timeline';
import { AskPage } from './pages/Ask';
import { ConsultationPage } from './pages/Consultation';
import { HistoryPage } from './pages/History';
import { Empty } from './components';

const navigation = [
  { to: '/', label: 'Обзор', icon: LayoutDashboard, end: true },
  { to: '/archive', label: 'Архив документов', icon: Archive },
  { to: '/timeline', label: 'Хронология', icon: Activity },
  { to: '/ask', label: 'Спросить архив', icon: MessageSquareText },
  { to: '/consultation', label: 'Для консультации', icon: BookOpen },
  { to: '/history', label: 'История изменений', icon: Clock3 },
];

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  useEffect(() => { setMenuOpen(false); window.scrollTo({ top: 0, behavior: 'instant' }); }, [location.pathname]);
  const current = navigation.find(item => item.end ? location.pathname === '/' : location.pathname.startsWith(item.to));
  return <div className="app-shell">
    <a className="skip-link" href="#main">Перейти к содержимому</a>
    {menuOpen && <button className="sidebar-backdrop" aria-label="Закрыть навигацию" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'open' : ''}`} aria-label="Основная навигация">
      <Link to="/" className="brand"><span className="brand-icon"><HeartPulse size={27} strokeWidth={1.7} /></span><span>Медархив<small>Личное пространство здоровья</small></span></Link>
      <button className="mobile-close icon-button" aria-label="Закрыть меню" onClick={() => setMenuOpen(false)}><X size={20} /></button>
      <Link className="button primary sidebar-add" to="/upload"><Plus size={19} /> Добавить документ</Link>
      <div className="nav-label">ВАШЕ ПРОСТРАНСТВО</div>
      <nav>{navigation.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={20} strokeWidth={1.7} /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-bottom"><div className="local-card"><span className="local-shield"><ShieldCheck size={23} /></span><strong>Только на вашем устройстве</strong><p>Документы и AI-обработка остаются локально.</p><span className="local-label"><i /> Локальный архив</span></div><a className="api-link" href="/docs" target="_blank" rel="noreferrer">Документация API <ArrowUpRight size={14} /></a><div className="sidebar-version">LOCAL MEDICAL ARCHIVE <span>v1.0</span></div></div>
    </aside>
    <div className="workspace"><div className="topbar"><div className="breadcrumb"><button className="mobile-menu icon-button" aria-label="Открыть меню" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={21} /></button><span>Мой архив</span><ChevronRight size={14} /><strong>{current?.label || (location.pathname === '/upload' ? 'Новый документ' : 'Документ')}</strong></div><div className="topbar-right"><ShieldCheck size={15} /><span>Локально и конфиденциально</span><div className="avatar" aria-label="Личный архив">МА</div></div></div>
      <main id="main" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/archive" element={<ArchivePage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/archive/:id" element={<DocumentPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/consultation" element={<ConsultationPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="*" element={<Empty title="Страница не найдена" action={<Link className="button primary" to="/">Вернуться к обзору</Link>}>Проверьте адрес или откройте главную страницу.</Empty>} />
        </Routes>
        <footer className="workspace-footer"><span><FilePlus2 size={14} /> Документы рядом. История под контролем.</span><span>AI-извлечения требуют проверки по источнику.</span></footer>
      </main>
    </div>
  </div>;
}
