import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('renders login page heading', () => {
    render(<App />);
    expect(screen.getByText(/Model Registry/i)).toBeInTheDocument();
  });
});
