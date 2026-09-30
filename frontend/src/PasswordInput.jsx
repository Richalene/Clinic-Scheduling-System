import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export default function PasswordInput(props) {
  const [visible, setVisible] = useState(false);
  return <span className="relative block"><input {...props} type={visible ? 'text' : 'password'} style={{ paddingRight: '3rem' }} /><button type="button" className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-muted hover:text-teal focus-visible:outline-2 focus-visible:outline-teal" aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18} /> : <Eye size={18} />}</button></span>;
}
