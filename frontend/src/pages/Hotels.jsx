import { useState } from 'react';
import { fetchApi } from '../lib/api';

function isoDate(date) {
    return date.toISOString().slice(0, 10);
}

function initialDates() {
    const checkIn = new Date();
    checkIn.setDate(checkIn.getDate() + 30);
    const checkOut = new Date(checkIn);
    checkOut.setDate(checkOut.getDate() + 2);
    return { checkIn: isoDate(checkIn), checkOut: isoDate(checkOut) };
}

function formatPrice(value, currency) {
    const amount = Number(value);
    if (!Number.isFinite(amount) || !currency) return 'Price unavailable';
    try {
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency,
            maximumFractionDigits: 2,
        }).format(amount);
    } catch {
        return `${amount.toFixed(2)} ${currency}`;
    }
}

export default function Hotels() {
    const [dates] = useState(initialDates);
    const [form, setForm] = useState({
        destination: '',
        check_in: dates.checkIn,
        check_out: dates.checkOut,
        adults: 2,
        rooms: 1,
        child_ages: '',
        currency: 'INR',
    });
    const [offers, setOffers] = useState([]);
    const [status, setStatus] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [checking, setChecking] = useState('');
    const [priceCheck, setPriceCheck] = useState(null);

    const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

    async function searchHotels(event) {
        event.preventDefault();
        setError('');
        setStatus('');
        setOffers([]);
        setPriceCheck(null);
        const ages = form.child_ages.trim()
            ? form.child_ages.split(',').map((age) => Number(age.trim()))
            : [];
        if (ages.some((age) => !Number.isInteger(age) || age < 0 || age > 17)) {
            setError('Enter child ages as comma-separated whole numbers from 0 to 17.');
            return;
        }
        setLoading(true);
        try {
            const result = await fetchApi('/hotels/search', {
                method: 'POST',
                body: JSON.stringify({
                    ...form,
                    adults: Number(form.adults),
                    rooms: Number(form.rooms),
                    child_ages: ages,
                }),
            });
            setOffers(result.offers || []);
            setStatus(result.status || 'no_results');
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setLoading(false);
        }
    }

    async function verifyOffer(offer) {
        setChecking(offer.offer_id);
        setPriceCheck(null);
        setError('');
        try {
            const result = await fetchApi(`/hotel-offers/${encodeURIComponent(offer.offer_id)}/price-check`, {
                method: 'POST',
                body: JSON.stringify({}),
            });
            setPriceCheck({ ...result, offerId: offer.offer_id });
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setChecking('');
        }
    }

    return (
        <div className="form-card">
            <div className="page-header">
                <div>
                    <div className="eyebrow">Live hotel search</div>
                    <h2>Find available stays</h2>
                    <p>Offers and prices come from Expedia Rapid when live mode and approved credentials are configured. Searching or checking an offer does not make a reservation.</p>
                </div>
            </div>
            <section className="card">
                <form onSubmit={searchHotels}>
                    <div className="form-grid">
                        <div className="field full">
                            <label htmlFor="hotel-destination">City or destination</label>
                            <input id="hotel-destination" value={form.destination} onChange={(event) => update('destination', event.target.value)} required minLength="2" maxLength="120" />
                        </div>
                        <div className="field">
                            <label htmlFor="hotel-checkin">Check-in</label>
                            <input id="hotel-checkin" type="date" value={form.check_in} onChange={(event) => update('check_in', event.target.value)} required />
                        </div>
                        <div className="field">
                            <label htmlFor="hotel-checkout">Check-out</label>
                            <input id="hotel-checkout" type="date" value={form.check_out} onChange={(event) => update('check_out', event.target.value)} required />
                        </div>
                        <div className="field">
                            <label htmlFor="hotel-adults">Adults</label>
                            <input id="hotel-adults" type="number" min="1" max="16" value={form.adults} onChange={(event) => update('adults', event.target.value)} required />
                        </div>
                        <div className="field">
                            <label htmlFor="hotel-rooms">Rooms</label>
                            <input id="hotel-rooms" type="number" min="1" max="8" value={form.rooms} onChange={(event) => update('rooms', event.target.value)} required />
                        </div>
                        <div className="field">
                            <label htmlFor="hotel-child-ages">Child ages (comma separated)</label>
                            <input id="hotel-child-ages" value={form.child_ages} onChange={(event) => update('child_ages', event.target.value)} placeholder="e.g. 4, 9" />
                        </div>
                        <div className="field">
                            <label htmlFor="hotel-currency">Currency</label>
                            <input id="hotel-currency" value={form.currency} onChange={(event) => update('currency', event.target.value.toUpperCase())} pattern="[A-Z]{3}" maxLength="3" required />
                        </div>
                    </div>
                    <div className="actions">
                        <button className="btn btn-primary" type="submit" disabled={loading}>
                            {loading ? 'Searching live inventory…' : 'Search available hotels'}
                        </button>
                    </div>
                </form>
            </section>
            {error && <div className="error" role="alert">{error}</div>}
            {!error && status === 'no_results' && <div className="card empty" role="status"><h3>No matching live offers</h3><p>The provider did not return available offers for these dates and occupancy.</p></div>}
            {offers.map((offer) => (
                <article className="card" key={offer.offer_id} style={{ marginTop: 16 }}>
                    <div className="page-header">
                        <div>
                            <div className="eyebrow">Expedia Rapid · Live offer</div>
                            <h3>{offer.hotel_name || 'Hotel name unavailable'}</h3>
                            <p>{[offer.address?.line_1, offer.address?.city, offer.address?.state_province_name, offer.address?.country_code].filter(Boolean).join(', ') || 'Address unavailable'}</p>
                        </div>
                        <strong>{formatPrice(offer.total_price, offer.currency)} total</strong>
                    </div>
                    <p>{offer.room_name || 'Room details unavailable'} · {offer.check_in} to {offer.check_out} · {offer.occupancy?.adults} adult(s), {offer.occupancy?.rooms} room(s)</p>
                    <p>{offer.refundable === true ? 'Refundable rate; review cancellation terms.' : offer.refundable === false ? 'Non-refundable rate.' : 'Refund policy unavailable.'}</p>
                    <p className="muted">Retrieved {new Date(offer.retrieved_at).toLocaleString()} · Availability and price can change; verify before proceeding.</p>
                    <button className="btn btn-secondary" type="button" disabled={checking === offer.offer_id} onClick={() => verifyOffer(offer)}>
                        {checking === offer.offer_id ? 'Verifying current price…' : 'Re-check price and availability'}
                    </button>
                    {priceCheck?.offerId === offer.offer_id && <div className="notice" role="status" style={{ marginTop: 12 }}>
                        {priceCheck.message} {priceCheck.current_pricing && <pre>{JSON.stringify(priceCheck.current_pricing, null, 2)}</pre>}
                        <p>This feature does not place or confirm a booking.</p>
                    </div>}
                </article>
            ))}
        </div>
    );
}
