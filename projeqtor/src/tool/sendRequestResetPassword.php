<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/
define('ANONYMOUS_ACCESS', true);
require_once "../tool/projeqtor.php";

if (sessionValueExists('currentLocale')) {
  scriptLog("resetPasswordRequest");
}
Sql::beginTransaction();

$resetEnabled = (Parameter::getGlobalParameter('passwordResetEnabled','NO')=='YES');
if (! $resetEnabled) {
  exit;
}

$login = trim(RequestHandler::getValue('login'));
$email = trim(RequestHandler::getValue('email'));

if (! $login || ! $email) {
  $result = i18n('messageMandatory', array(i18n('colLogin') . '/' . i18n('colEmail')));
  $result.= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  displayLastOperationStatus($result);
  exit;
}

$user = new User();
$user = SqlElement::getSingleSqlElementFromCriteria('User', array('name' => $login));

if (! $user || ! $user->id) {
  traceLog("RESET_PASSWORD - invalid login [$login]");
  $result = i18n('messageInvalidLoginOrEmail');
  $result.= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  displayLastOperationStatus($result);
  exit;
}

if (! $user->email || pq_strtolower(trim($user->email)) != pq_strtolower($email)) {
  traceLog("RESET_PASSWORD - login/email mismatch for user #$user->id");
  $result = i18n('messageInvalidLoginOrEmail');
  $result.= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  displayLastOperationStatus($result);
  exit;
}

$paramLdap_allow_login = Parameter::getGlobalParameter('paramLdap_allow_login');
if ($user->idle!=0) {
  $result = i18n("colUser") . ' ' . i18n("colLocked");
  $result.= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  displayLastOperationStatus($result);
  exit;
}
if ($user->isLdap!=0 && isset($paramLdap_allow_login) && pq_strtolower($paramLdap_allow_login)=='true') {
  $result = i18n("errorResetPasswordLdapUser");
  $result.= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  displayLastOperationStatus($result);
  exit;
}

// Limite : 3 demandes max par 24h
$now = new DateTime();
$limitDate = clone $now;
$limitDate->modify('-1 day');

$cn = Sql::getConnection();
$pwdRR = new PasswordResetRequest();
$table = $pwdRR->getDatabaseTableName();
$query = "SELECT COUNT(*) AS nb
          FROM " . $table . "
          WHERE idUser = " . Sql::fmtId($user->id) . "
            AND requestDateTime >= '" . $limitDate->format('Y-m-d H:i:s') . "'";

$res = Sql::query($query, $cn);
$line = Sql::fetchLine($res);
$nb = ($line) ? $line['nb'] : 0;

if ($nb >= 3) {
  traceLog("RESET_PASSWORD - too many requests for user #$user->id");
  $result = i18n('messageTooManyPasswordResetRequests');
  $result.= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  displayLastOperationStatus($result);
  exit;
}

$pwdRRList = $pwdRR->getSqlElementsFromCriteria(array('idUser'=>$user->id, 'email'=>$email));
foreach ($pwdRRList as $pwd){
  $pwd->used = 1;
  $pwd->save();
}

// Génération du token (hash sha1)
$raw = '';
for ($i=0; $i<10; $i++) {
  $raw .= mt_rand(0, 999999);
}
$raw .= uniqid('', true) . session_id() . $now->format('YmdHis');
$token = sha1($raw);

$req = new PasswordResetRequest();
$req->idUser = $user->id;
$req->email = $email;
$req->requestDateTime = $now->format('Y-m-d H:i:s');
$req->token = $token;
$req->used = 0;
$save = $req->save();

if (getLastOperationStatus($save)!='OK') {
  traceLog("RESET_PASSWORD - cannot save request for user #$user->id");
  displayLastOperationStatus($save);
  exit;
}

// Construire l’URL de reset
$scheme = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS']=='on') ? 'https://' : 'http://';
$host   = $_SERVER['HTTP_HOST'];
$root   = getAppRoot();
$resetUrl = $scheme . $host . $root . '/view/resetPasswordChangeView.php?token=' . urlencode($token);

// Envoi du mail
$instance=Parameter::getGlobalParameter('paramDbDisplayName');
$subject="[$instance] ".i18n('mailResetPasswordSubject');
$link = '<a rel="noopener" href="'.$resetUrl.'" target="_blank">'.i18n('mailResetPasswordLink').'</a>';
$adminEmail = Parameter::getGlobalParameter('paramAdminMail');
$body = i18n('mailResetPasswordBody', array($user->name, $link, $adminEmail));

$mailSent = sendMail($email, $subject, $body);

if (! $mailSent) {
  traceLog("RESET_PASSWORD - mail not sent to [$email]");
  $result = i18n('colActionKO');
  $result.= '<input type="hidden" id="lastOperationStatus" value="ERROR" />';
  displayLastOperationStatus($result);
  exit;
}

$result = i18n('messageResetPasswordEmailSent');
$result.= '<input type="hidden" id="lastOperationStatus" value="OK" />';
displayLastOperationStatus($result);
