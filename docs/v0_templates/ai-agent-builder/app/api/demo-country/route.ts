export async function GET(request: Request) {
  if (process.env.VERCEL_ENV !== 'production') { 
    return Response.json({
      country: 'US',
      message: `Hello from US!`,
    })
  }
  
  const country = request.headers.get('x-vercel-ip-country');
  return Response.json({
    country,
    message: `Hello from ${country}!`,
  })
}
