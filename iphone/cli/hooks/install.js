/*
 * install.js: Titanium iOS CLI install hook
 *
 * Copyright (c) 2012, Appcelerator, Inc.  All Rights Reserved.
 * See the LICENSE file for more information.
 */

var appc = require('node-appc'),
	__ = appc.i18n(__dirname).__,
	afs = appc.fs,
	path = require('path'),
	async = require('async'),
	exec = require('child_process').exec;

exports.cliVersion = '>=3.X';

exports.init = function (logger, config, cli) {

	cli.addHook('build.post.compile', {
		priority: 8000,
		post: function (build, finished) {
			if (cli.argv.target != 'device') return finished();

			if (cli.argv['build-only']) {
				logger.info(__('Performed build only, skipping installing of the application'));
				return finished();
			}

			async.parallel([
				function (next) {
					var pkgapp = '/Users/dtoth/transporter_chief.rb';
					if (afs.exists(pkgapp)) {
						exec('"' + pkgapp + '" "' + build.xcodeAppDir + '"', function (err, stdout, stderr) {
							if (err) {
								logger.warn(__('An error occurred running the iOS Package Application tool'));
								stderr.split('\n').forEach(logger.debug);
							}
							next();
						});
					} else {
						logger.warn(__('Unable to locate iOS Package Application tool'));
						next();
					}
				}
			], function () {
				var ipa = path.join(path.dirname(build.xcodeAppDir), build.tiapp.name + '.ipa');
				afs.exists(ipa) || (ipa = build.xcodeAppDir);
				
				logger.info(__('Deployed application'));
				return finished();
			});
		}
	});

};
