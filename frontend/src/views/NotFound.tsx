import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="p-8 text-center">
      <h1 className="text-2xl font-semibold text-cyan-400 mb-2">Page not found</h1>
      <p className="text-zinc-500 mb-4">The page you requested does not exist.</p>
      <Link to="/" className="text-cyan-400 hover:underline">Go to Live view</Link>
    </div>
  );
}
