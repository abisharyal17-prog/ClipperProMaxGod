import { Link, Route, Routes } from "react-router-dom";

import { Layout } from "./components/common/Layout";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";
import Workspace from "./pages/Workspace";

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <p className="text-title text-text">Page not found</p>
      <p className="text-body text-muted">The page you are looking for does not exist.</p>
      <Link
        to="/"
        className="text-body font-medium text-accent transition-colors duration-150 ease-out hover:underline"
      >
        Back to projects
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/p/:id" element={<Workspace />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
