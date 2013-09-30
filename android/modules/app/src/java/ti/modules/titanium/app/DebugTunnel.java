package ti.modules.titanium.app;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;

/**
 * Tunnels debug data so that the debugger behaves the same way on iOS and
 * Android.
 * 
 * @author Dawson Toth
 */
public class DebugTunnel {
	private volatile Socket localSocket;
	private volatile Socket remoteSocket;
	private Thread localToRemote;
	private Thread remoteToLocal;

	public DebugTunnel(String remoteHost, int remotePort) {
		try {
			localSocket = new Socket("0.0.0.0", 61337);
			remoteSocket = new Socket(remoteHost, remotePort);
			localToRemote = createThread(localSocket.getInputStream(), remoteSocket.getOutputStream());
			remoteToLocal = createThread(remoteSocket.getInputStream(), localSocket.getOutputStream());
			localToRemote.start();
			remoteToLocal.start();
		} catch (Exception e) {
			e.printStackTrace();
			stop();
		}
	}

	private Thread createThread(final InputStream input, final OutputStream output) {
		return new Thread() {
			public void run() {
				byte[] buffer = new byte[1024];
				int bytesRead;
				try {
					while ((bytesRead = input.read(buffer)) != -1) {
						output.write(buffer, 0, bytesRead);
					}
				} catch (IOException e) {
					e.printStackTrace();
				}
			}
		};
	}

	public void stop() {
		try {
			localSocket.close();
			localSocket = null;
			localToRemote.interrupt();
			localToRemote = null;
		} catch (Exception e) {
			// Oh well.
		}
		try {
			remoteSocket.close();
			remoteSocket = null;
			remoteToLocal.interrupt();
			remoteToLocal = null;
		} catch (Exception e) {
			// Oh well.
		}
	}
}
