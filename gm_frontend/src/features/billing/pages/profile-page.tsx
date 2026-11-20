import PasswordForm from '../components/password-form'
import PaymentMethodsSection from '../components/payment-methods-section'
import ProfileInfoForm from '../components/profile-info-form'

export default function ProfilePage() {
  return (
    <div className="max-w-4xl space-y-6 px-6 pb-20 pt-7 text-white sm:px-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Mi perfil</h1>
        <p className="mt-1 text-sm text-muted">
          Administra tu identidad, contraseña y métodos de pago.
        </p>
      </header>

      <ProfileInfoForm />
      <PasswordForm />
      <PaymentMethodsSection />
    </div>
  )
}
