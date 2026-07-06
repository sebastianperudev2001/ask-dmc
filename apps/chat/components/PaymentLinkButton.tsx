type PaymentLinkButtonProps = {
  checkoutUrl: string
}

const PaymentLinkButton = ({ checkoutUrl }: PaymentLinkButtonProps) => (
  <a
    href={checkoutUrl}
    target="_blank"
    rel="noopener noreferrer"
    data-testid="payment-link-button"
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      marginTop: 10,
      padding: '10px 18px',
      borderRadius: 10,
      background: 'var(--color-accent)',
      color: 'var(--color-brand)',
      fontSize: 13.5,
      fontWeight: 700,
      textDecoration: 'none',
    }}
  >
    Haz clic aquí para pagar →
  </a>
)

export default PaymentLinkButton
