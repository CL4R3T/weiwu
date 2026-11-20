import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title:'维雾主义',description:'看目录，猜词条。禁止搜索的中文维基猜谜游戏。',icons:{icon:'/favicon.svg'}};
export default function RootLayout({children}:{children:React.ReactNode}) {return <html lang="zh-CN"><body>{children}</body></html>}
