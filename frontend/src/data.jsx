import { createContext, useContext, useEffect, useState } from 'react';
import { all } from './api';
import { Loading, Notice } from './components';

const CatalogContext = createContext(null);
export const useCatalogs = () => useContext(CatalogContext);

export function CatalogProvider({ children }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    const names = ['services', 'patients', 'rooms', 'equipment', 'staff'];
    Promise.all(names.map((name) => all(`/${name}/`, controller.signal)))
      .then((values) => { if (!controller.signal.aborted) setData(Object.fromEntries(names.map((name, i) => [name, values[i]]))); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [revision]);
  if (error) return <div className="dash-panel"><Notice>{error}</Notice><button className="button button-secondary" onClick={() => setRevision((n) => n + 1)}>Try again</button></div>;
  if (!data) return <Loading />;
  return <CatalogContext.Provider value={{ ...data, refresh: () => setRevision((n) => n + 1), addPatient: (patient) => setData((old) => ({ ...old, patients: [...old.patients, patient] })) }}>{children}</CatalogContext.Provider>;
}

export function useList(path) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    all(path, controller.signal).then((data) => {
      if (!controller.signal.aborted) setRows(data);
    }).catch((err) => {
      if (!controller.signal.aborted) setError(err.message);
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, revision]);
  return { rows, loading, error, reload: () => setRevision((n) => n + 1), setRows };
}
