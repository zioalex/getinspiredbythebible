import { redirect } from 'next/navigation';
import { headers } from 'next/headers';
import { getPreferredLocale } from '@/lib/locale-detection';

// Redirect `/` to the best matching locale based on Accept-Language
export default async function RootPage() {
  const headersList = await headers();
  const acceptLanguage = headersList.get('accept-language');
  const locale = getPreferredLocale(acceptLanguage);
  redirect(`/${locale}`);
}
