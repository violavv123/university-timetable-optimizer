import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { Button } from "../components/ui";

export function NotFoundPage() {
  return <main className="not-found"><div className="brand-mark"><Icon name="calendar" /></div><p className="eyebrow">404 · Page not found</p><h1>This slot is not on the timetable.</h1><p>The page may have moved, or the address may be incorrect.</p><Link to="/dashboard"><Button icon="home">Back to overview</Button></Link></main>;
}
